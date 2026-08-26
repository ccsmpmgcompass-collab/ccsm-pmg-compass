// test_area_capsules.js — "Cómo Ayudar a Cada Área", the per-area capsules
// that replaced the 28-metric detail panel at the foot of every zone and
// district leadership section.
//
// WHY THIS EXISTS. The old panel printed all 28 nightly metrics for every
// area: 432px an area, 4,730px in a zone letter, 41% of the whole letter, and
// not one verdict attached to any of it. A district leader reading "34
// lecciones" had to already know what a normal week looked like in their zone
// to know whether that was good. The capsule prints four numbers, colours them
// against the unit's own median, and says in one sentence what to do about
// them — 1,139px for the same zone.
//
// Everything asserted below guards a place where a plausible-looking capsule
// would tell a leader something untrue:
//
//   - A RATE WITH NO DENOMINATOR IS NOT ZERO. a1a_buildStats stores it as 0,
//     which is right for a table cell and wrong here: an area that taught
//     nobody has no invitation rate at all, and reading it as 0% paints it
//     red, drags the unit median down and invents a finding. The capsule
//     recomputes from the raw counts so "no basis" stays apart from "zero".
//   - A SUPERLATIVE IS A CLAIM ABOUT EVERY OTHER AREA. "La más baja de la
//     zona" is checked against the whole unit before it is written, and a tie
//     makes it false for both areas holding it — two areas that invited nobody
//     is the live case, because 0 is the floor and ties constantly.
//   - AN IMPOSSIBLE NUMBER IS NOT A STRENGTH. An area reporting more
//     significant conversations than contacts gets a warning; ranking that
//     same 129% as its best indicator would have the block praise a number it
//     is questioning three lines below.
//   - ONE AREA REPORTING MAKES THE MEDIAN THAT AREA. Every comparison then
//     reads 0% away from itself, so the block says there is nothing to compare
//     against instead of printing a verdict built on one row.
//   - THE GROUP KEY LEADS THE SORT. Sorting by days while grouping by district
//     prints a district chip above every single area, which is not a grouping.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet } = require('./fixtures');
const assert = require('assert');

// Agent1A rides along because A1A_FRACTION_RATE_KEYS decides what each rate's
// numerator and denominator are. The capsule reads it at render time rather
// than keeping a second copy, so a test that stubbed it would test the copy.
const GS_FILES = ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
                  'CCSM_Agent3.gs', 'CCSM_Agent1A.gs', 'CCSM_Agent1C.gs'];

const env = makeGasEnv();
const scope = loadGs(GS_FILES, env.globals);
makeCcsmSpreadsheet(env, scope); // a1c_buildEmail's footer calls getMissionName()

const GREEN = '#16a34a', BLUE = '#2563eb', YELLOW = '#a16207', RED = '#dc2626', MUTED = '#6b7280';
const STRONG = '#166534', WEAK = '#b91c1c';
const LEADER_EMAIL = 'lider@missionary.org';
const WEEK_END = new Date(2026, 7, 23);

const C = {
  header: '#1e3a5f', green: GREEN, blue: BLUE, yellow: YELLOW, red: RED,
  muted: MUTED, border: '#e5e7eb', bgLight: '#f9fafb',
};

/**
 * The prose a leader reads. <strong> comes out with NO space in its place —
 * the diagnosis sentences bold a phrase mid-clause ("...convierte: <strong>28
 * lecciones...</strong>.") and turning the tags into spaces would put one
 * before the full stop, so every sentence assertion below would have to be
 * written against punctuation that is not on the page.
 */
function textOf(html) {
  return html.replace(/<\/?strong>/g, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

/** One area's stats in a1a_buildStats' shape, from the six counts that matter here. */
function stats(days, attempted, made, mc, lessons, invites) {
  return {
    submissions: days,
    contacts_attempted: attempted,
    contacts_made: made,
    meaningful_conversations: mc,
    friend_lessons: lessons,
    baptismal_invitations: invites,
    // The rates a1a_buildStats would have stored alongside them — deliberately
    // present, and deliberately 0 for the no-denominator cases, so anything
    // reading area.stats[rate] instead of the raw counts is caught here.
    contact_rate: attempted > 0 ? made / attempted : 0,
    mc_rate:      made > 0 ? mc / made : 0,
    lesson_rate:  attempted > 0 ? lessons / attempted : 0,
    close_rate:   lessons > 0 ? invites / lessons : 0,
    effort_score: 2.5,
  };
}

function area(name, district, s) {
  return { name: name, zone: 'Zona Uno', district: district, stats: s,
           growth: null, strength1: null, strength2: null };
}

/**
 * One area's capsule, from its name to the start of the next one. Negative
 * assertions have to be scoped this way: the block renders every area in the
 * unit, so "Galvarino is not praised for its conversation rate" is trivially
 * satisfied — or wrongly tripped — by a sentence belonging to another area.
 */
function capsuleOf(html, name) {
  const from = html.indexOf('>' + name + '<');
  const rest = html.slice(from);
  const next = rest.indexOf('<div style="border:1px solid');
  const end  = rest.indexOf('Sin informe esta semana');
  const cut  = [next, end].filter((i) => i > 0);
  return cut.length ? rest.slice(0, Math.min.apply(null, cut)) : rest;
}

/** The block on its own, straight from the builder. */
function block(areas, ki, scopeName) {
  return scope.a1c_buildAreaCapsules_(areas, ki === undefined ? null : ki,
                                      scopeName || 'zone', C);
}

// ── The zone the sentences below are measured against ───────────────────────
// Five reporting areas. Alfa and Beta are identical and anchor every median;
// the other three each land on a different diagnosis rule.
//
//         ipd   contacto  conv.sig.  lecciones  invitación
//  Alfa    20     50%        50%       20,0%       25%
//  Beta    20     50%        50%       20,0%       25%
//  Volumen 40     50%        50%       10,0%        0%    ← volume, no conversion
//  Embudo  20     20%        75%       10,0%       28,6%  ← funnel cut at step one
//  Justa   22     50%        50%       19,7%       19,2%  ← generic: best and worst
//  median  20     50%        50%       19,7%       25%
const ZONE = [
  area('Alfa',    'Uno', stats(7, 140,  70, 35, 28, 7)),
  area('Beta',    'Uno', stats(7, 140,  70, 35, 28, 7)),
  area('Volumen', 'Dos', stats(7, 280, 140, 70, 28, 0)),
  area('Embudo',  'Dos', stats(7, 140,  28, 21, 14, 4)),
  area('Justa',   'Dos', stats(6, 132,  66, 33, 26, 5)),
];

// ── 1 · The diagnosis rules, each on its own ────────────────────────────────
{
  const t = textOf(block(ZONE));

  // 1 · Works the hardest of the unit, converts the least. Both superlatives
  // are true here: Volumen alone holds the highest ipd and alone holds a zero
  // invitation rate.
  assert.ok(t.includes(
    'La que más trabaja de la zona y la que menos convierte: 28 lecciones, ' +
    'ninguna invitación al bautismo.'), 'rule 1 (volume, no conversion)');

  // 2 · The funnel is cut at the first step, and the second clause recognises
  // an area that contacts little but deeply.
  assert.ok(t.includes(
    'El embudo se corta en el primer paso: tasa de contacto 20%, la más baja ' +
    'de la zona. Contacta poco pero profundo: 75% de conversaciones significativas.'),
    'rule 2 (funnel cut at step one, + deep-contact clause)');

  // 4 · Nothing under the median: no invented weakness, and never "por encima
  // de la mediana" of a number that is exactly on it.
  assert.ok(t.includes(
    'Sin ningún número bajo la mediana de la zona. Su margen más ajustado es ' +
    'el volumen de contacto (20,0).'), 'rule 4 (nothing below the median)');
  assert.ok(!/único punto bajo es el volumen de contacto, 0%/.test(t),
    'rule 4 must not call a margin at or above the median a "punto bajo"');

  // 5 · The general case: the best number and the one to attend to, each with
  // its own sign.
  assert.ok(t.includes(
    'Fuerte en el volumen de contacto (22,0, 10% sobre la zona). A atender: ' +
    'la tasa de invitación bautismal (19%, 23% bajo la zona).'), 'rule 5 (generic)');
}

// ── 2 · Rule 3, rule 4b, tied superlatives, and an area below everywhere ────
{
  // Teaches but does not invite: close_rate is the weakest indicator, there
  // were lessons, and there were no invitations at all.
  const teaches = ZONE.concat([area('Enseña', 'Dos', stats(7, 140, 70, 35, 42, 0))]);
  const t = textOf(block(teaches));
  assert.ok(t.includes(
    'Enseña pero no invita: 42 lecciones con amigos y ninguna invitación al ' +
    'bautismo esta semana.'), 'rule 3 (teaches without inviting)');

  // With two areas at close_rate 0 the superlatives in rule 1 are no longer
  // true of either, so Volumen loses them and keeps the finding.
  assert.ok(t.includes('Mucho trabajo y poca conversión: 28 lecciones, ninguna invitación al bautismo.'),
    'a tied minimum drops the superlative and keeps the finding');
  assert.ok(!t.includes('La que más trabaja de la zona y la que menos convierte'),
    'a tied minimum must not be reported as "la que menos convierte"');

  // 4b · Strong across the funnel with one soft spot, between -15% and 0.
  const soft = ZONE.concat([area('Suave', 'Dos', stats(7, 140, 63, 32, 28, 7))]);
  assert.ok(/Sólida en todo el embudo\. Su único punto bajo es la tasa de contacto, \d+% bajo la zona\./
    .test(textOf(block(soft))), 'rule 4b (one soft spot)');

  // An area whose BEST number is still under the median is told that, not
  // congratulated on it.
  const under = [
    area('Alfa', 'D', stats(7, 140, 70, 35, 28, 7)),
    area('Beta', 'D', stats(7, 140, 70, 35, 28, 7)),
    area('Baja', 'D', stats(7, 105, 45, 22, 15, 3)),
  ];
  const u = textOf(block(under, null, 'district'));
  assert.ok(/Su mejor número es .+, y aun así \d+% bajo el distrito\. A atender: /.test(u),
    'an all-below area is not told it is "fuerte en" anything');
  assert.ok(!u.includes('Fuerte en'), 'no praise where every number is under the median');
}

// ── 3 · A rate with no denominator is "—", never 0% ──────────────────────────
{
  // Sin Enseñar taught nobody, so it has no invitation rate. area.stats says
  // close_rate 0 (a1a_buildStats' own default); the capsule must not believe it.
  const areas = ZONE.concat([area('Sin Enseñar', 'Dos', stats(7, 140, 70, 35, 0, 0))]);
  const html = block(areas);
  const capsule = capsuleOf(html, 'Sin Enseñar');
  const cells = capsule.match(/font-size:13px;font-weight:700;color:(#[0-9a-f]{6});">([^<]*)</g) || [];
  assert.ok(cells.length >= 4, 'the strip renders four numbers');
  const invitation = cells[3];
  assert.ok(invitation.includes('>—<'), 'no lessons ⇒ no invitation rate, printed as a dash');
  assert.ok(!invitation.includes('>0%<'), 'a missing denominator must not print as 0%');
  assert.ok(invitation.includes('color:' + MUTED), 'a number with no basis is muted, not red');

  // And it stays out of the median. Read as 0 it would pull the invitation
  // median from 25% down to 22%, and Justa — whose own rate never moved —
  // would be told it is 13% under the zone instead of 23%.
  assert.ok(textOf(html).includes('A atender: la tasa de invitación bautismal (19%, 23% bajo la zona).'),
    'an indicator with no basis must not move the unit median');
}

// ── 4 · Colours are taken from the unit median ──────────────────────────────
{
  // Intentos per reporting day: Alto 80, Alfa/Beta 40, Suave 32, Bajo 24,
  // Cero 0 — median 36. The whole unit works well above what any fixed
  // mission target would call normal, which is the point: 40 int./día is an
  // ordinary week HERE, and a threshold that did not read the unit would paint
  // Alfa and Beta green while their leader is looking for who to help.
  const areas = [
    area('Alfa',  'D', stats(7, 280, 140, 70,  56, 14)),
    area('Beta',  'D', stats(7, 280, 140, 70,  56, 14)),
    area('Alto',  'D', stats(7, 560, 280, 140, 112, 28)),
    area('Suave', 'D', stats(7, 224, 112, 56,  45, 11)),
    area('Bajo',  'D', stats(7, 168,  84, 42,  34,  8)),
    area('Cero',  'D', stats(7,   0,   0,  0,   0,  0)),
  ];
  const html = block(areas, null, 'district');
  const ipdColor = (name) => (capsuleOf(html, name)
    .match(/font-size:13px;font-weight:700;color:(#[0-9a-f]{6});/) || [])[1];
  assert.strictEqual(ipdColor('Alto'),  STRONG, '+20% or more over the median reads strong');
  assert.strictEqual(ipdColor('Alfa'),  MUTED,  'inside the dead band reads neutral');
  assert.strictEqual(ipdColor('Suave'), YELLOW, '10-30% under the median reads soft');
  assert.strictEqual(ipdColor('Bajo'),  WEAK,   'more than 30% under the median reads weak');
  assert.strictEqual(ipdColor('Cero'),  WEAK,   'a real zero is weak whatever the median says');
  // Not the letter's C.green: these are 13px text on white, where #16a34a
  // scores 3.0:1 and #dc2626 4.26:1, both under AA.
  assert.ok(!html.includes('color:' + GREEN + ';">'), 'strip numbers use the AA-safe green');
}

// ── 5 · Sort: district first, then fewest days, then name ───────────────────
{
  const areas = [
    area('Zeta',  'Dos', stats(7, 140, 70, 35, 28, 7)),
    area('Alfa',  'Uno', stats(7, 140, 70, 35, 28, 7)),
    area('Omega', 'Dos', stats(3,  60, 30, 15, 12, 3)),
    area('Beta',  'Uno', stats(2,  40, 20, 10,  8, 2)),
  ];
  const html = block(areas);
  const order = (html.match(/>(Alfa|Beta|Zeta|Omega)</g) || []).map((s) => s.slice(1, -1));
  assert.deepStrictEqual(order, ['Omega', 'Zeta', 'Beta', 'Alfa'],
    'district groups first, and inside each the fewest days lead');

  // One chip per district, not one per area — the bug that shipped once when
  // the sort was by days and the grouping by district.
  assert.deepStrictEqual(html.match(/📍 Distrito [^<]*/g), ['📍 Distrito Dos', '📍 Distrito Uno'],
    'exactly one district chip per district, in reading order');

  // A district letter has one district, so the chip is a zone device and must
  // not lead the sort where it does not render.
  const dl = block(areas, null, 'district');
  assert.ok(!dl.includes('📍 Distrito'), 'no district chip in a district letter');
  assert.deepStrictEqual((dl.match(/>(Alfa|Beta|Zeta|Omega)</g) || []).map((s) => s.slice(1, -1)),
    ['Beta', 'Omega', 'Alfa', 'Zeta'], 'without the chip, days lead the sort');

  // The days chip bands.
  const chipColor = (name) => (capsuleOf(html, name)
    .match(/font-size:9px;color:(#[0-9a-f]{6});text-align:right/) || [])[1];
  assert.strictEqual(chipColor('Alfa'),  GREEN,  '7 días reads green');
  assert.strictEqual(chipColor('Omega'), YELLOW, 'under 5 días reads yellow');
  assert.strictEqual(chipColor('Beta'),  YELLOW, '2 días reads yellow');
}

// ── 6 · Silent areas collapse into one row, and name what else they owe ─────
{
  const areas = ZONE.concat([
    area('Muda Uno', 'Dos', stats(0, 0, 0, 0, 0, 0)),
    area('Muda Dos', 'Uno', stats(0, 0, 0, 0, 0, 0)),
  ]);
  const ki = { metaWeekEnd: '2026-08-16', silentAreas: ['Muda Dos'] };
  const html = block(areas, ki);

  assert.strictEqual((html.match(/\/7 días/g) || []).length, 5,
    'a silent area gets no capsule of its own');
  assert.ok(html.includes('Sin informe esta semana'), 'the silent group is headed');
  const t = textOf(html);
  assert.ok(t.includes('Muda Dos · Muda Uno'), 'silent areas are listed together, sorted');
  assert.ok(t.includes('0 de 7 días. Muda Dos además fijó meta el 16 de agosto y no informó resultado.'),
    'the one that also owes a weekly result is named, on the meta week');

  // Derived from ki.silentAreas, not from being dark on the nightly form: an
  // area can miss every night and still have filed its weekly indicators.
  assert.ok(!textOf(block(areas, { metaWeekEnd: '2026-08-16', silentAreas: [] }))
    .includes('además fijó meta'), 'no meta sentence when nobody owes a weekly result');
  assert.ok(!textOf(block(areas, null)).includes('además fijó meta'),
    'no meta sentence when the KI roll-up is unavailable');

  // Plural.
  assert.ok(textOf(block(areas, { metaWeekEnd: '2026-08-16', silentAreas: ['Muda Dos', 'Muda Uno'] }))
    .includes('además fijaron meta el 16 de agosto y no informaron resultado.'),
    'two areas take the plural');
}

// ── 7 · The impossible count: warned about, and never ranked as a strength ──
{
  // 36 significant conversations against 28 contacts — the live Galvarino week.
  const areas = ZONE.concat([area('Galvarino', 'Dos', stats(6, 88, 28, 36, 23, 1))]);
  const g = textOf(capsuleOf(block(areas), 'Galvarino'));

  assert.ok(g.includes('⚠ 36 conversaciones significativas contra 28 contactos. Una conversación ' +
    'significativa es parte de un contacto, así que conviene revisar cómo se está contando.'),
    'the mismatch is put as a counting question');
  assert.ok(!/inflad|falso|incorrect|error|mal inform/i.test(g), 'never worded as an accusation');
  assert.ok(!g.includes('Fuerte en la tasa de conversaciones significativas'),
    "a 129% rate is not ranked as this area's strength");
  assert.ok(!g.includes('Contacta poco pero profundo'),
    'nor used to praise the depth of its contacting');
  // But it is still shown: hiding it would leave the warning talking about a
  // number the reader cannot see anywhere.
  assert.ok(g.includes('36 conversaciones significativas contra 28'), 'the reported counts stay visible');

  assert.strictEqual(textOf(block(ZONE)).includes('⚠'), false, 'no warning where the counts hold');
}

// ── 8 · One reporting area has nothing to be compared against ───────────────
{
  const areas = [
    area('Sola', 'D', stats(7, 140, 70, 35, 28, 7)),
    area('Muda', 'D', stats(0, 0, 0, 0, 0, 0)),
  ];
  const t = textOf(block(areas, null, 'district'));
  assert.ok(t.includes('Es la única área que informó esta semana, así que todavía no hay con qué ' +
    'comparar sus números.'), 'the only area that reported is told there is no comparison');
  assert.ok(!/sobre el distrito|bajo el distrito|Sin ningún número bajo la mediana/.test(t),
    'no verdict is built from a median that is the area itself');
}

// ── 9 · Scope wording, and the block wired into the letter ──────────────────
{
  assert.ok(textOf(block(ZONE, null, 'zone')).includes('comparados con la mediana de la zona.'),
    'a zone letter compares against the zone');
  assert.ok(textOf(block(ZONE, null, 'district')).includes('comparados con la mediana del distrito.'),
    'a district letter contracts the article');
  assert.strictEqual(block([], null, 'zone'), '', 'no areas, no block');

  const AREAS = {
    'Alfa':   Object.assign({}, ZONE[0], { ki: null }),
    'Beta':   Object.assign({}, ZONE[1], { ki: null }),
    'Embudo': Object.assign({}, ZONE[3], { ki: null, district: 'Dos' }),
  };
  const ROLE = {
    zone:     { Is_ZL: 'TRUE',  Is_DL: 'FALSE', Is_AP: 'FALSE' },
    district: { Is_ZL: 'FALSE', Is_DL: 'TRUE',  Is_AP: 'FALSE' },
    mission:  { Is_ZL: 'FALSE', Is_DL: 'FALSE', Is_AP: 'TRUE'  },
  };
  function letter(scopeName) {
    const totals = { total_areas: 3, submitted: 3, contacts_made: 168 };
    const summaries = {
      mission:   Object.assign({}, totals),
      zones:     { 'Zona Uno': Object.assign({}, totals) },
      districts: { 'Uno': Object.assign({}, totals) },
    };
    const person = scope.a1c_buildPeopleMap([Object.assign({
      Area_Name: 'Alfa', Zone: 'Zona Uno', District: 'Uno',
      Companion1_Name: 'Elder Uno', Companion1_Email: LEADER_EMAIL,
      Companion2_Name: '', Companion2_Email: '',
      Is_STL: 'FALSE', Is_MP: 'FALSE', Active: 'TRUE',
    }, ROLE[scopeName])])[LEADER_EMAIL];
    return scope.a1c_buildEmail(person, AREAS, summaries, WEEK_END);
  }

  const zl = letter('zone');
  assert.ok(zl.includes('Cómo Ayudar a Cada Área'), 'the block is wired into the zone letter');
  assert.ok(textOf(zl).includes('El embudo se corta en el primer paso'),
    'and reaches the diagnosis through the real call site');
  assert.ok(letter('district').includes('Cómo Ayudar a Cada Área'), 'and into the district letter');
  assert.ok(!letter('mission').includes('Cómo Ayudar a Cada Área'),
    'the mission letter carries no capsules — 43 of them is not a page');

  // The 28-metric dump this replaced is gone from every letter, headings and
  // per-area metric sections included.
  ['zone', 'district', 'mission'].forEach(function (s) {
    const html = letter(s);
    assert.ok(!html.includes('Detalle de Áreas'), 'the old detail panel heading is gone (' + s + ')');
    assert.ok(!html.includes('Esfuerzo y Cumplimiento'),
      'and its per-area metric sections with it (' + s + ')');
  });
  assert.strictEqual(typeof scope.a1c_buildAreaDetailPanel_, 'undefined',
    'the old builder is removed, not left unreferenced');
}

console.log('area capsules OK');
