// test_leader_ki_block.js — the Key Indicators block that now OPENS every
// leadership section (a1a_rollUpKi_ -> summaries.*.ki -> a1c_buildLeaderKiBlock_).
//
// WHY THIS EXISTS. A leader's letter used to open on nightly activity totals —
// contacts, conversations, doors — while the seven goals their areas actually
// set for themselves appeared nowhere. This block puts the unit's own metas
// first. Agent1A decides which areas count and which week's meta each is
// measured against (tested in test_agent1a_ki_rollup.js); everything here is
// about rendering that decision honestly, and every assertion below guards a
// place where a plausible-looking number would mislead the reader:
//
//   - The meta is the one filed a WEEK EARLIER. A meta on a WEEKLY_KI row is
//     next week's plan — the weekly form says so in as many words — so the
//     sub-caption must date the metas at metaWeekEnd, never at the week being
//     reported. This changes verdicts, not just wording.
//   - Areas that filed nothing are NAMED, not silently dropped into a smaller
//     total that reads as a worse week.
//   - Areas falling back to their own same-week meta are marked with a dagger.
//     A mixed rule the reader cannot see is a bug from where they sit.
//   - The verdict tiles carry the GOAL-BAND colour, not a fixed green. The
//     design mockup hardcoded green, which would paint a zone that met none of
//     its seven metas in the same green as one that met all seven. Locked in
//     below so it cannot drift back.
//   - `ki === null` (WEEKLY_KI unreadable) renders NOTHING, matching area.ki:
//     a source outage must never be reported as a unit that failed.
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

const GREEN = '#16a34a', BLUE = '#2563eb', YELLOW = '#a16207', RED = '#dc2626', MUTED = '#6b7280';
const LEADER_EMAIL = 'lider@missionary.org';
const WEEK_END = new Date(2026, 7, 23);
const META_WEEK = '2026-08-16';
const META_LABEL = '16 de agosto';

const KI_DISPLAYS = [
  'Nuevas Personas Encontradas', 'Lecciones con Miembros',
  'Amigos en la Reunión Sacramental', 'Amigos en la Iglesia (Primera Semana)',
  'Amigos con Fecha Bautismal', 'Bautizados y Confirmados',
  'Conversos Recientes en la Iglesia',
];

/** A roll-up in the exact shape a1a_rollUpKi_ returns. `pairs` is [real, meta] per indicator. */
function rollup(pairs, over) {
  const indicators = KI_DISPLAYS.map((display, i) => {
    const real = pairs[i][0], meta = pairs[i][1];
    return { key: 'ki_' + i, display: display, real: real, meta: meta,
             achieved: meta > 0 && real >= meta };
  });
  const base = {
    metaWeekEnd:   META_WEEK,
    areasTotal:    11,
    areasReported: 7,
    metasSet:      indicators.filter((i) => i.meta > 0).length,
    metasAchieved: indicators.filter((i) => i.achieved).length,
    fallbackAreas: [],
    silentAreas:   [],
    indicators:    indicators,
  };
  return Object.assign(base, over || {});
}

// The Los Angeles Norte week the design was measured against: 4 of 7 metas met.
const LAN = [[78, 75], [52, 52], [20, 20], [2, 8], [2, 9], [1, 1], [16, 25]];

const AREAS = {
  'Área Uno': {
    zone: 'Zona Uno', district: 'Distrito Uno',
    stats: { submissions: 7, contacts_made: 40, meaningful_conversations: 20,
             new_people_found: 5, friend_lessons: 12, baptismal_invitations: 1,
             effort_score: 2.4 },
    growth: { key: 'contact_rate', display: 'Enfoque' },
    strength1: null, strength2: null,
    // null keeps the MISSIONARY KI block silent, so every "Indicadores Clave"
    // string asserted below belongs to the leadership block under test.
    ki: null,
  },
};

const ROLE_FLAGS = {
  zone:     { Is_ZL: 'TRUE',  Is_DL: 'FALSE', Is_AP: 'FALSE' },
  district: { Is_ZL: 'FALSE', Is_DL: 'TRUE',  Is_AP: 'FALSE' },
  mission:  { Is_ZL: 'FALSE', Is_DL: 'FALSE', Is_AP: 'TRUE'  },
};

/** Renders one leader's whole letter with `ki` hung on the summary for `scopeName`. */
function render(scopeName, ki) {
  const totals = { total_areas: 11, submitted: 7, contacts_made: 40 };
  const summaries = {
    mission:   Object.assign({}, totals),
    zones:     { 'Zona Uno':     Object.assign({}, totals) },
    districts: { 'Distrito Uno': Object.assign({}, totals) },
  };
  const target = scopeName === 'mission' ? summaries.mission
               : scopeName === 'zone'    ? summaries.zones['Zona Uno']
               :                           summaries.districts['Distrito Uno'];
  if (ki !== undefined) target.ki = ki;

  const person = scope.a1c_buildPeopleMap([Object.assign({
    Area_Name: 'Área Uno', Zone: 'Zona Uno', District: 'Distrito Uno',
    Companion1_Name: 'Elder Uno', Companion1_Email: LEADER_EMAIL,
    Companion2_Name: '', Companion2_Email: '',
    Is_STL: 'FALSE', Is_MP: 'FALSE', Active: 'TRUE',
  }, ROLE_FLAGS[scopeName])])[LEADER_EMAIL];

  return scope.a1c_buildEmail(person, AREAS, summaries, WEEK_END);
}

// The glossary at the foot of every letter defines the term "Indicadores
// Clave" too, so the block is always located by its full scoped title.
const TITLE = {
  zone:     'Indicadores Clave de la Zona',
  district: 'Indicadores Clave del Distrito',
  mission:  'Indicadores Clave de la Misión',
};

// The letter's palette, mirroring the C object a1c_buildEmail passes down.
// Only the block under test is rendered from it, so the negative assertions
// below cannot be satisfied — or tripped — by anything elsewhere in the letter.
const C = {
  header: '#1e3a5f', green: GREEN, blue: BLUE, yellow: YELLOW, red: RED,
  muted: MUTED, border: '#e5e7eb', bgLight: '#f9fafb',
};

/** The block on its own, straight from the builder. */
function block(ki, scopeName) {
  return scope.a1c_buildLeaderKiBlock_(ki, scopeName || 'zone', C);
}

/** The block's text, tags stripped — for prose assertions that ignore markup. */
function textOf(html) {
  assert.ok(html.indexOf('Indicadores Clave') !== -1, 'expected a KI block to render');
  return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
}

// ===========================================================================
// 1. WEEKLY_KI unreadable -> the block renders NOTHING.
//    A missing source is a fact about the source. Rendering seven zeros would
//    tell a zone it earned nothing in a week it may have worked hard.
// ===========================================================================
{
  [null, undefined].forEach((absent) => {
    const html = render('zone', absent);
    assert.strictEqual(html.indexOf(TITLE.zone), -1,
      'ki=' + String(absent) + ' must render no KI block at all');
    // Positive control: the rest of the leadership section still renders, so
    // this is not passing because the whole letter vanished.
    assert.ok(html.indexOf('Resumen de Zona — Zona Uno') !== -1,
      'the leadership section itself must still render');
    assert.ok(html.indexOf('Reportaron') !== -1, 'the KPI tiles must still render');
  });
  console.log('unreadable source renders no block OK');
}

// ===========================================================================
// 2. Real data: title, dated sub-caption, both tiles, all 7 rows.
// ===========================================================================
{
  const html = block(rollup(LAN));
  const text = textOf(html);

  assert.ok(html.includes(TITLE.zone), 'expected the zone-scoped title');

  // THE LOAD-BEARING ASSERTION: the metas are dated to the week they were
  // filed (weekEnd - 7), not to the week being reported.
  assert.ok(text.includes('las metas que las áreas fijaron el ' + META_LABEL),
    'the sub-caption must date the metas at metaWeekEnd, not at the reported week');
  assert.ok(!text.includes('23 de agosto'),
    'the reported week must never be presented as the week the metas were set');

  assert.ok(text.includes('4 / 7') && text.includes('Metas alcanzadas'),
    'expected the metas-achieved tile');
  assert.ok(text.includes('7 / 11') && text.includes('Áreas que informaron'),
    'expected the areas-reported tile');

  KI_DISPLAYS.forEach((d) => {
    assert.ok(html.includes(d), 'expected KI row "' + d + '"');
  });
  [[78, 75], [52, 52], [16, 25], [2, 9]].forEach((p) => {
    assert.ok(text.includes(p[0] + ' / ' + p[1]), 'expected the pair ' + p[0] + ' / ' + p[1]);
  });

  assert.ok(text.includes('Meta alcanzada'), 'expected a met-goal caption');
  assert.ok(text.includes('64% de la meta'), 'expected 16/25 to render as 64% of the meta');
  assert.ok(text.includes('Los totales suman las 7 áreas que informaron'),
    'the footnote must say how many areas the totals cover');

  console.log('real roll-up renders OK');
}

// ===========================================================================
// 3. Rows are ordered metas-met first, then closest to met; an indicator
//    nobody set a meta for has no standing in either group and sorts last.
// ===========================================================================
{
  // real/meta: 100%, 10%, 120%, no meta, 90%, 50%, 0%
  const html = block(rollup([[5, 5], [1, 10], [12, 10], [3, 0], [9, 10], [5, 10], [0, 4]]));
  const order = KI_DISPLAYS
    .map((d) => ({ d: d, at: html.indexOf('>' + d + '<') }))
    .sort((a, b) => a.at - b.at)
    .map((x) => KI_DISPLAYS.indexOf(x.d));

  assert.deepStrictEqual(order, [2, 0, 4, 5, 1, 6, 3],
    'expected achieved-first (120%, 100%), then 90/50/10/0, then the unset meta last');

  const text = textOf(html, 'zone');
  assert.ok(text.includes('ninguna área fijó meta para este indicador'),
    'an indicator with no meta anywhere must say so, never show 0% or a fake goal');
  assert.ok(!text.includes('3 / 0'), 'a zero meta must not render as a real/0 pair');

  console.log('row ordering OK');
}

// ===========================================================================
// 4. Areas that set a meta and filed nothing are NAMED, and their meta is
//    explicitly excluded from the totals. Singular and plural both read.
// ===========================================================================
{
  const one = textOf(block(rollup(LAN, { silentAreas: ['Villa Obispo'] })));
  assert.ok(one.includes('1 área fijó meta el ' + META_LABEL + ' y no informó resultado'),
    'expected the singular callout wording');
  assert.ok(one.includes('Villa Obispo'), 'the silent area must be named');
  assert.ok(one.includes('Su meta no entra en los totales de abajo'),
    'the callout must state that the missing meta is excluded');

  const many = textOf(block(rollup(LAN, { silentAreas: ['Lautaro 1', 'Vilcun'] })));
  assert.ok(many.includes('2 áreas fijaron meta el ' + META_LABEL + ' y no informaron resultado'),
    'expected the plural callout wording');
  assert.ok(many.includes('Lautaro 1') && many.includes('Vilcun'),
    'every silent area must be named');

  const none = textOf(block(rollup(LAN)));
  assert.ok(!none.includes('no informó resultado') && !none.includes('no informaron resultado'),
    'no callout may render when every area with a meta reported');

  // A name is held together by a literal U+00A0 so a narrow phone cannot break
  // it across two lines. It must be the character, not '&nbsp;' — that goes
  // through a1c_esc, which escapes the ampersand and prints the entity as text.
  // Checked against the raw HTML: textOf's \s+ collapse eats U+00A0.
  const rawOne = block(rollup(LAN, { silentAreas: ['Villa Obispo'] }));
  assert.ok(rawOne.includes('Villa Obispo'),
    'the area name must be joined by a literal non-breaking space');
  assert.ok(!rawOne.includes('Villa&nbsp;Obispo') && !rawOne.includes('Villa&amp;nbsp;Obispo'),
    'the entity form would be escaped and printed verbatim in the letter');

  console.log('silent-area callout OK');
}

// ===========================================================================
// 5. Fallback areas (filed this week, no meta last week) are daggered in the
//    sub-caption and named in the footnote. Absent when there are none.
// ===========================================================================
{
  const many = textOf(block(rollup(LAN,
    { fallbackAreas: ['Bosque Mar 1', 'Catrihuala 2'] })));
  assert.ok(many.includes('fijaron el ' + META_LABEL + '.†'),
    'the dagger must sit on the very claim it qualifies');
  assert.ok(many.includes('† 2 áreas no habían fijado meta el ' + META_LABEL),
    'expected the plural fallback footnote');
  assert.ok(many.includes('cuentan con la meta que fijaron esta semana'),
    'the footnote must say which meta was used instead');
  assert.ok(many.includes('Bosque Mar 1') && many.includes('Catrihuala 2'),
    'every fallback area must be named');

  const one = textOf(block(rollup(LAN, { fallbackAreas: ['Catrihuala 2'] })));
  assert.ok(one.includes('† 1 área no había fijado meta') && one.includes('cuenta con la meta que fijó esta semana'),
    'expected the singular fallback footnote');

  const none = textOf(block(rollup(LAN)));
  assert.ok(!none.includes('†'),
    'no dagger may appear when every area was measured against a prior-week meta');

  console.log('fallback dagger OK');
}

// ===========================================================================
// 6. The verdict tiles carry the goal band, NOT a fixed colour. This is a
//    deliberate departure from the approved mockup's hardcoded green: a zone
//    that met none of its metas must not wear the same colour as one that met
//    them all.
// ===========================================================================
{
  function tileColors(html) {
    return html.slice(0, html.indexOf('</table>'))
      .match(/background:(#[0-9a-f]{6});border-radius:6px/g)
      .map((m) => m.slice(11, 18));
  }

  const allMet  = tileColors(block(rollup(
    [[5, 5], [5, 5], [5, 5], [5, 5], [5, 5], [5, 5], [5, 5]], { areasReported: 11 })));
  assert.strictEqual(allMet[0], GREEN, '7 of 7 metas met must be green');
  assert.strictEqual(allMet[1], GREEN, '11 of 11 areas reporting must be green');

  const noneMet = tileColors(block(rollup(
    [[0, 5], [0, 5], [0, 5], [0, 5], [0, 5], [0, 5], [0, 5]])));
  assert.strictEqual(noneMet[0], RED,
    '0 of 7 metas met must be RED — a hardcoded green here would praise a zone for missing everything');
  assert.strictEqual(noneMet[1], BLUE, '7 of 11 areas reporting is in progress, not a failure');

  const lan = tileColors(block(rollup(LAN)));
  assert.strictEqual(lan[0], BLUE, '4 of 7 (57%) sits in the blue band');

  // 3 of 7 = 43% -> yellow. Proves all four bands are reachable from the tile.
  const few = tileColors(block(rollup(
    [[5, 5], [5, 5], [5, 5], [0, 5], [0, 5], [0, 5], [0, 5]])));
  assert.strictEqual(few[0], YELLOW, '3 of 7 (43%) must be yellow');

  console.log('tile colours follow the goal bands OK');
}

// ===========================================================================
// 7. A unit where nobody filed: no rows of zeros, a plain statement instead,
//    and a dash rather than "0 / 0" on the metas tile.
// ===========================================================================
{
  const ki = rollup([[0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
    { areasReported: 0, areasTotal: 3, silentAreas: ['Área Dos'] });
  const html = block(ki);
  const text = textOf(html);

  assert.ok(text.includes('Ninguna de las 3 áreas envió su informe semanal de indicadores'),
    'a unit with no reports must say so plainly');
  assert.ok(!text.includes('0 / 0'),
    '"0 / 0 Metas alcanzadas" reads as a broken tile; it must render a dash');
  assert.ok(!text.includes('de la meta'),
    'no percentage rows may render when there is nothing to compare');
  assert.ok(!text.includes('Los totales suman'),
    'no totals footnote when there are no totals');
  // The silent area is still named — that is the actionable part.
  assert.ok(text.includes('Área Dos'), 'the silent area must still be named');
  // Positive control.
  assert.ok(html.includes(TITLE.zone), 'the block itself must still render');

  console.log('no-reports unit OK');
}

// ===========================================================================
// 8. Placement and scope wording. The block opens the leadership section —
//    ahead of the AI narrative and the nightly KPI tiles — at all three
//    scopes, and the title agrees with its article ("del Distrito").
// ===========================================================================
{
  const EXPECTED = TITLE;
  Object.keys(EXPECTED).forEach((s) => {
    const html = render(s, rollup(LAN));
    assert.ok(html.includes(EXPECTED[s]), s + ': expected the title "' + EXPECTED[s] + '"');
    assert.ok(!html.includes('de el Distrito'), s + ': the article must contract to "del"');
    assert.ok(!/Indicadores Clave (de la|del) (mission|zone|district)/.test(html),
      s + ': the raw English scope token must never reach the letter');

    const heading = html.indexOf('Resumen de');
    const block   = html.indexOf(EXPECTED[s]);
    const tiles   = html.indexOf('Reportaron');
    assert.ok(heading < block, s + ': the block belongs inside the leadership section');
    assert.ok(block < tiles,
      s + ': the unit\'s own metas must lead, above the nightly activity tiles');
  });

  console.log('placement and scope wording OK');
}

console.log('\ntest_leader_ki_block: all checks passed');
