// test_rumbo_block.js — "El Rumbo de la Zona", the trend block that now sits
// directly under the Key Indicators in every leadership section
// (a1a_rollUpTrend_ -> summaries.*.trend -> a1c_buildRumboBlock_).
//
// WHY THIS EXISTS. A leader could see one week's verdict and nothing about
// direction, so a bad week and a bad trend read identically. The block answers
// "which way is this going", and almost every rule in it exists because the
// obvious version of that answer is wrong on this mission's real data:
//
//   - RAW WEEKLY TOTALS LIE. Reporting volume swings ~20% week to week here.
//     Los Angeles Norte's church invitations fell 9% in raw totals the same
//     week they rose 9% per reporting day. Everything is therefore per
//     reporting day, the day counts are printed, and the flip is named.
//   - A UNIT'S RATE IS NOT THE MEAN OF ITS AREAS' RATES. One companionship
//     that attempted a single contact and made it has a 100% contact rate;
//     averaged in, it moves a zone as much as an area that attempted 200.
//   - effort_score IS ALREADY AN AVERAGE, so it rolls up weighted by the
//     nights behind it, and an area with no score is left out rather than
//     counted as a zero the 1-3 scale cannot produce.
//   - THE FEATURED CHAIN IS CHOSEN FROM THE DATA — the weakest Key Indicator
//     that has a nightly chain — so it follows the week rather than a
//     hardcoded indicator, and never features a goal that was met.
//   - A DEAD BAND SEPARATES MOVEMENT FROM NOISE, and a "sin cambio" chip
//     carries its own sign, because ■ says nothing about direction.
//
// The Los Angeles Norte week below is the one the design was measured and
// approved against; block 5 reproduces the approved block number for number.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

function loadScope(files) {
  const env = makeGasEnv();
  const scope = loadGs(files, env.globals);
  return { env, scope };
}

// Agent1A rides along because A1A_KI_FEEDERS and A1A_TREND_FUNNEL_KEYS are the
// single source of truth for what feeds what and what gets trended — the block
// reads them at render time rather than keeping a second copy.
const { env, scope } = loadScope(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
   'CCSM_Agent3.gs', 'CCSM_Agent1A.gs', 'CCSM_Agent1C.gs']);
makeCcsmSpreadsheet(env, scope); // a1c_buildEmail's footer calls getMissionName()

const GREEN = '#16a34a', BLUE = '#2563eb', YELLOW = '#a16207', RED = '#dc2626', MUTED = '#6b7280';
const UP = '#166534', DOWN_TEXT = '#b91c1c';
const LEADER_EMAIL = 'lider@missionary.org';
const WEEK_END = new Date(2026, 7, 23);

const C = {
  header: '#1e3a5f', green: GREEN, blue: BLUE, yellow: YELLOW, red: RED,
  muted: MUTED, border: '#e5e7eb', bgLight: '#f9fafb',
};

/** Tags stripped, whitespace collapsed — for prose assertions that ignore markup. */
function textOf(html) {
  return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

/**
 * One week in the shape a1a_rollUpTrend_ emits. The 4 fraction rates are
 * DERIVED from the counts here with the same num/den formula the roll-up uses,
 * so a fixture can never quietly disagree with the thing it is standing in for.
 */
function week(w, days, counts, effort) {
  const m = {};
  scope.A1A_TREND_COUNT_KEYS.forEach((k) => { m[k] = counts[k] || 0; });
  scope.A1A_RATE_METRICS.forEach((r) => {
    if (!r.num || !r.den) return;
    m[r.key] = m[r.den] > 0 ? Math.round(m[r.num] / m[r.den] * 1000) / 1000 : 0;
  });
  m.effort_score = (effort === undefined) ? null : effort;
  return { week: w, days: days, metrics: m };
}

const EMPTY_WEEK = (w) => week(w, 0, {}, undefined);

// ── The real Los Angeles Norte week (2026-08-17 → 23), from the live sheet ──
// 54 area-days reported the week before, 45 this week. Every number below was
// read off the live dump; the per-day figures they produce are the ones on the
// approved mockup.
const LAN_TREND = { weeks: [
  EMPTY_WEEK('2026-08-02'),
  EMPTY_WEEK('2026-08-09'),
  week('2026-08-16', 54, {
    contacts_attempted: 976, contacts_made: 419, meaningful_conversations: 207,
    new_people_found: 70, friend_lessons: 118, church_invites: 184,
    baptismal_invitations: 2, baptism_doctrine_lessons: 13, baptismal_calendars: 2,
  }, 2.17),
  week('2026-08-23', 45, {
    contacts_attempted: 1079, contacts_made: 459, meaningful_conversations: 263,
    new_people_found: 81, friend_lessons: 176, church_invites: 167,
    baptismal_invitations: 12, baptism_doctrine_lessons: 39, baptismal_calendars: 5,
  }, 2.48),
] };

const KI_DEFS = [
  ['ki_new_people', 'Nuevas Personas Encontradas'],
  ['ki_member_lessons', 'Lecciones con Miembros'],
  ['ki_friends_sacrament', 'Amigos en la Reunión Sacramental'],
  ['ki_friends_first_week', 'Amigos en la Iglesia (Primera Semana)'],
  ['ki_baptismal_date', 'Amigos con Fecha Bautismal'],
  ['ki_baptized_confirmed', 'Bautizados y Confirmados'],
  ['ki_rc_at_church', 'Conversos Recientes en la Iglesia'],
];

/** A KI roll-up in a1a_rollUpKi_'s shape. `pairs` is [real, meta] per indicator. */
function ki(pairs) {
  return {
    metaWeekEnd: '2026-08-16', areasTotal: 11, areasReported: 7,
    fallbackAreas: [], silentAreas: [],
    metasSet: pairs.filter((p) => p[1] > 0).length,
    metasAchieved: pairs.filter((p) => p[1] > 0 && p[0] >= p[1]).length,
    indicators: KI_DEFS.map((d, i) => ({
      key: d[0], display: d[1], real: pairs[i][0], meta: pairs[i][1],
      achieved: pairs[i][1] > 0 && pairs[i][0] >= pairs[i][1],
    })),
  };
}

// Los Angeles Norte's own week: 4 of 7 metas met, weakest is
// "Amigos con Fecha Bautismal" at 2 of 9.
const LAN_KI = ki([[78, 75], [52, 52], [20, 20], [1, 1], [2, 9], [0, 0], [2, 8]]);

const rumbo = (trend, kiRollup, s) => scope.a1c_buildRumboBlock_(trend, kiRollup, s || 'zone', C);

// ===========================================================================
// 1. a1a_rollUpTrend_: a unit's rate comes from its OWN numerator and
//    denominator, never from the mean of its areas' rates.
// ===========================================================================
{
  const weeks = ['2026-08-23'];
  const history = { byArea: {
    // 1 attempt, 1 contact -> a 100% contact rate on its own
    'Área Chica':  { '2026-08-23': { submissions: 1, contacts_attempted: 1, contacts_made: 1 } },
    // 199 attempts, 40 contacts -> ~20%
    'Área Grande': { '2026-08-23': { submissions: 7, contacts_attempted: 199, contacts_made: 40 } },
  } };
  const members = [{ name: 'Área Chica' }, { name: 'Área Grande' }];
  const out = scope.a1a_rollUpTrend_(members, history, weeks);

  assert.strictEqual(out.weeks.length, 1);
  const w = out.weeks[0];
  assert.strictEqual(w.days, 8, 'days are area-days summed across the unit');
  assert.strictEqual(w.metrics.contacts_attempted, 200);
  assert.strictEqual(w.metrics.contacts_made, 41);
  assert.strictEqual(w.metrics.contact_rate, 0.205, '41 / 200, the rate the zone actually ran at');
  assert.ok(w.metrics.contact_rate < 0.3,
    'averaging the two AREA rates would give ~0.60 and flatter the zone threefold');

  console.log('unit rates come from summed num/den OK');
}

// ===========================================================================
// 2. a1a_rollUpTrend_: effort_score is weighted by the nights behind it, and
//    an area with no score at all is excluded from BOTH sides rather than
//    counted as a zero — which is not a value the 1-3 scale can produce.
// ===========================================================================
{
  const weeks = ['2026-08-23'];
  const history = { byArea: {
    'Uno':  { '2026-08-23': { submissions: 1, effort_score: 3, contacts_made: 5 } },
    'Dos':  { '2026-08-23': { submissions: 7, effort_score: 2, contacts_made: 5 } },
    'Tres': { '2026-08-23': { submissions: 7, contacts_made: 5 } }, // reported, no effort answer
  } };
  const members = [{ name: 'Uno' }, { name: 'Dos' }, { name: 'Tres' }];
  const w = scope.a1a_rollUpTrend_(members, history, weeks).weeks[0];

  assert.strictEqual(w.days, 15, 'the score-less area still reported, so it still counts as days');
  assert.strictEqual(w.metrics.contacts_made, 15);
  assert.strictEqual(w.metrics.effort_score, 2.13, '(3x1 + 2x7) / 8');
  assert.notStrictEqual(w.metrics.effort_score, 2.5, 'a straight mean of the two area scores');
  assert.ok(w.metrics.effort_score > 2,
    'counting the score-less area as a zero would drag this to ~1.13');

  console.log('effort_score weighting and exclusion OK');
}

// ===========================================================================
// 3. a1a_rollUpTrend_ edges: nothing to roll up returns null, and a week the
//    unit never reported is zeros with a NULL effort score, not a zero one.
// ===========================================================================
{
  const history = { byArea: { 'Uno': { '2026-08-23': { submissions: 3, contacts_made: 9 } } } };
  const members = [{ name: 'Uno' }];

  assert.strictEqual(scope.a1a_rollUpTrend_([], history, ['2026-08-23']), null, 'no members');
  assert.strictEqual(scope.a1a_rollUpTrend_(members, null, ['2026-08-23']), null, 'no history');
  assert.strictEqual(scope.a1a_rollUpTrend_(members, history, []), null, 'no weeks');

  const out = scope.a1a_rollUpTrend_(members, history, ['2026-08-16', '2026-08-23']);
  assert.strictEqual(out.weeks[0].days, 0);
  assert.strictEqual(out.weeks[0].metrics.contacts_made, 0);
  assert.strictEqual(out.weeks[0].metrics.effort_score, null,
    'a week with no reports has no effort score; 0 would read as the worst possible week');
  assert.strictEqual(out.weeks[1].days, 3);

  console.log('roll-up edge cases OK');
}

// ===========================================================================
// 4. The carried metric list covers everything that reads it. A feeder the
//    roll-up does not carry would render an EMPTY featured chain rather than
//    an error, which is exactly the kind of silence this project keeps
//    getting burned by.
// ===========================================================================
{
  const carried = scope.A1A_TREND_COUNT_KEYS;
  Object.keys(scope.A1A_KI_FEEDERS).forEach((kiKey) => {
    scope.A1A_KI_FEEDERS[kiKey].forEach((m) => {
      assert.ok(carried.indexOf(m) !== -1,
        kiKey + ' feeds on ' + m + ', which A1A_TREND_COUNT_KEYS does not carry');
    });
  });
  scope.A1A_TREND_FUNNEL_KEYS.forEach((m) => {
    assert.ok(carried.indexOf(m) !== -1, 'the funnel list names ' + m + ', which is not carried');
  });
  scope.A1A_RATE_METRICS.forEach((r) => {
    if (!r.num || !r.den) return;
    assert.ok(carried.indexOf(r.num) !== -1 && carried.indexOf(r.den) !== -1,
      r.key + ' is derived from ' + r.num + ' / ' + r.den + ', which must both be carried');
  });
  assert.strictEqual(carried.length, new Set(carried).size, 'the union must not repeat a key');

  console.log('carried metric list covers every reader OK');
}

// ===========================================================================
// 5. The approved Los Angeles Norte block, number for number — including the
//    sign flip that is the whole reason the block is per reporting day.
//    184 -> 167 church invitations is MINUS 9% raw and PLUS 9% per day.
// ===========================================================================
{
  const html = rumbo(LAN_TREND, LAN_KI);
  const t = textOf(html);

  assert.ok(t.includes('El Rumbo de la Zona'), 'scoped title');
  assert.ok(t.includes('Promedio por día informado, contra la semana del 16 de agosto'),
    'the basis and the week compared against are stated up front');
  assert.ok(t.includes('10 de 11 indicadores al alza'),
    '11 grouped indicators — the 12th, baptismal invitations, is in the featured chain');
  assert.ok(t.includes('ninguno a la baja esta semana'));

  // The featured chain: the weakest Key Indicator and the three numbers behind it.
  assert.ok(t.includes('La cadena más débil'));
  assert.ok(t.includes('Amigos con Fecha Bautismal: 2 de 9.'),
    'the weakest indicator, not the first or the lowest raw number');
  assert.ok(t.includes('Estos son los tres números que la producen — y los tres van subiendo.'));
  [['Lecciones de Doctrina del Bautismo', '0,87', '▲ 260%'],
   ['Invitaciones al Bautismo', '0,27', '▲ 620%'],
   ['Calendarios Bautismales Entregados', '0,11', '▲ 200%']].forEach(([label, val, chip]) => {
    assert.ok(t.includes(label), 'featured row missing: ' + label);
    assert.ok(t.includes(val), label + ': expected the per-day value ' + val);
    assert.ok(t.includes(chip), label + ': expected the delta chip ' + chip);
  });

  // The grouped lists, per day.
  [['Lecciones con Amigos', '3,9', '▲ 79%'],
   ['Conversaciones Significativas', '5,8', '▲ 52%'],
   ['Nuevas Personas Encontradas', '1,8', '▲ 39%'],
   ['Intentos de Contacto', '24,0', '▲ 33%'],
   ['Contactos', '10,2', '▲ 31%'],
   ['Invitaciones a la Iglesia', '3,7', '▲ 9%'],
   ['Tasa de Conversaciones Significativas', '57,3%', '▲ 7,9 pp'],
   ['Tasa de Invitación Bautismal', '6,8%', '▲ 5,1 pp'],
   ['Tasa de Lecciones', '16,3%', '▲ 4,2 pp']].forEach(([label, val, chip]) => {
    assert.ok(t.includes(val + ' ' + chip), label + ': expected "' + val + ' ' + chip + '"');
  });

  // The flat band keeps its sign: "■ 0,4 pp" cannot be told from a rise.
  assert.ok(t.includes('42,5% ■ −0,4 pp'),
    'a rate that fell four tenths of a point is flat, and says which way it moved');
  assert.ok(t.includes('Ningún indicador bajó esta semana.'),
    'an empty group says so; a heading followed by nothing reads as a rendering fault');

  // The footnote states the basis and names the flip in the reader's own terms.
  assert.ok(t.includes('la zona informó 45 días esta semana y 54 la anterior'));
  assert.ok(t.includes('los totales crudos no son comparables'));
  assert.ok(t.includes('En crudo, Invitaciones a la Iglesia bajaría 9%'),
    'the one metric whose raw total says the opposite must be named');

  // Nothing is counted twice: a featured metric leaves the grouped lists.
  const invites = html.split('Invitaciones al Bautismo').length - 1;
  assert.strictEqual(invites, 1,
    'baptismal invitations belong to the featured chain only, or the verdict double-counts');

  console.log('approved Los Angeles Norte block reproduced OK');
}

// ===========================================================================
// 6. Choosing the featured chain. It is the weakest indicator THAT HAS a
//    nightly chain; a met goal is never "the weakest chain"; and with no
//    candidate at all the box is dropped and every metric groups instead.
// ===========================================================================
{
  // Bautizados y Confirmados is the weakest at 0 of 10, but the nightly form
  // collects nothing that feeds it, so the block moves to the next weakest.
  const noFeeder = ki([[78, 75], [52, 52], [20, 20], [1, 1], [4, 9], [0, 10], [2, 8]]);
  const t1 = textOf(rumbo(LAN_TREND, noFeeder));
  assert.ok(!t1.includes('Bautizados y Confirmados'),
    'an indicator with no nightly chain cannot be featured');
  assert.ok(t1.includes('Conversos Recientes en la Iglesia: 2 de 8.'),
    'the next weakest indicator that does have a chain is featured instead');

  // Every goal met: there is no weak chain to warn about.
  const allMet = ki([[78, 75], [52, 52], [20, 20], [1, 1], [9, 9], [10, 10], [8, 8]]);
  const t2 = textOf(rumbo(LAN_TREND, allMet));
  assert.ok(!t2.includes('La cadena más débil'),
    'a unit that met every meta must not be shown a "weakest chain" warning');
  assert.ok(t2.includes('de 12 indicadores al alza'),
    'with nothing featured, all 12 metrics group');

  // No KI roll-up at all (WEEKLY_KI unreadable): the trend still stands alone.
  const t3 = textOf(rumbo(LAN_TREND, null));
  assert.ok(!t3.includes('La cadena más débil'));
  assert.ok(t3.includes('de 12 indicadores al alza'));
  assert.ok(t3.includes('El Rumbo de la Zona'), 'the trend does not depend on the KI block');

  // One feeder reads as one number, in the singular.
  const sacrament = ki([[78, 75], [52, 52], [10, 20], [1, 1], [9, 9], [10, 10], [8, 8]]);
  const t4 = textOf(rumbo(LAN_TREND, sacrament));
  assert.ok(t4.includes('Este es el número que la produce'),
    'one feeder must not read "Estos son los 1 números"');

  console.log('featured chain selection OK');
}

// ===========================================================================
// 7. The verdict tile follows a1c_goalBandColor_, the letter's one colour
//    authority — the same reason Part 2's Key Indicator tiles do. A fixed
//    green would give a unit where nothing rose the tile of a unit where
//    everything did.
// ===========================================================================
{
  // Everything falls: 45 days this week against 54, with every count halved.
  const falling = { weeks: [
    EMPTY_WEEK('2026-08-02'), EMPTY_WEEK('2026-08-09'),
    week('2026-08-16', 54, {
      contacts_attempted: 976, contacts_made: 500, meaningful_conversations: 300,
      new_people_found: 70, friend_lessons: 118, church_invites: 184,
      baptismal_invitations: 20, baptism_doctrine_lessons: 13, baptismal_calendars: 2,
    }, 2.9),
    week('2026-08-23', 54, {
      contacts_attempted: 200, contacts_made: 60, meaningful_conversations: 20,
      new_people_found: 5, friend_lessons: 8, church_invites: 10,
      baptismal_invitations: 1, baptism_doctrine_lessons: 1, baptismal_calendars: 0,
    }, 1.5),
  ] };
  const down = rumbo(falling, null);
  assert.ok(textOf(down).includes('0 de 12 indicadores al alza'));
  assert.ok(down.includes('background:' + RED + ';border-radius:6px'),
    'nothing rising must not be painted the colour of everything rising');
  assert.ok(textOf(down).includes('Ningún indicador subió esta semana.'));
  assert.ok(!textOf(down).includes('ninguno a la baja esta semana'),
    'the subtitle must not claim nothing fell when everything did');

  const up = rumbo(LAN_TREND, LAN_KI);
  assert.ok(up.includes('background:' + GREEN + ';border-radius:6px'),
    '10 of 11 rising is 91% — the green band');

  // The three group headings are text on white and must clear AA at 11px,
  // which C.green (3.0:1) and C.red (4.26:1) do not.
  assert.ok(up.includes('color:' + UP + ';text-transform:uppercase'), 'Subiendo heading');
  assert.ok(up.includes('color:' + DOWN_TEXT + ';text-transform:uppercase'), 'Bajando heading');
  assert.ok(up.includes('color:' + YELLOW + ';text-transform:uppercase'), 'Sin cambio heading');

  console.log('verdict banding and heading contrast OK');
}

// ===========================================================================
// 8. Not enough history to show a direction. "The history does not exist yet"
//    and "nothing moved" are different facts and must not render the same.
// ===========================================================================
{
  assert.strictEqual(rumbo(null, LAN_KI), '', 'no roll-up at all renders nothing');
  assert.strictEqual(rumbo({ weeks: [LAN_TREND.weeks[3]] }, LAN_KI), '',
    'a single week is not a trend');

  // Last week nobody reported.
  const noPrev = { weeks: [EMPTY_WEEK('2026-08-16'), LAN_TREND.weeks[3]] };
  const t1 = textOf(rumbo(noPrev, LAN_KI));
  assert.ok(t1.includes('El Rumbo de la Zona'), 'the heading still explains what is missing');
  assert.ok(t1.includes('Todavía no hay una semana anterior con la que comparar'));
  assert.ok(t1.includes('16 de agosto'), 'and dates the week it could not find');
  assert.ok(!t1.includes('indicadores al alza'), 'no verdict can be drawn from one week');

  // This week nobody reported.
  const noCur = { weeks: [LAN_TREND.weeks[2], EMPTY_WEEK('2026-08-23')] };
  const t2 = textOf(rumbo(noCur, LAN_KI));
  assert.ok(t2.includes('no registró informes nocturnos, así que todavía no hay un rumbo que medir'));

  // A count that was zero last week has no percent change to report.
  const fromZero = { weeks: [
    week('2026-08-16', 7, { contacts_attempted: 100, contacts_made: 50, baptismal_invitations: 0 }, 2),
    week('2026-08-23', 7, { contacts_attempted: 100, contacts_made: 50, baptismal_invitations: 4 }, 2),
  ] };
  const t3 = textOf(rumbo(fromZero, null));
  assert.ok(t3.includes('▲ desde 0'), 'a rise from nothing is said in words, not as Infinity');
  assert.ok(!/Infinity|NaN/.test(t3), 'no arithmetic artefact may reach the letter');

  // A single reported day still reads as Spanish.
  const oneDay = { weeks: [
    week('2026-08-16', 7, { contacts_attempted: 70, contacts_made: 35 }, 2),
    week('2026-08-23', 1, { contacts_attempted: 15, contacts_made: 9 }, 2),
  ] };
  assert.ok(textOf(rumbo(oneDay, null)).includes('informó 1 día esta semana'),
    'the naive version prints "informó 1 días"');

  console.log('missing-history and edge wording OK');
}

// ===========================================================================
// 9. End to end. The block is unreachable unless a1c_buildLeadershipSection
//    passes summaries.*.trend through, and runAgent1A is what puts it there —
//    every check above can pass with the call site unwired.
// ===========================================================================
{
  // (a) Through the real letter builder, at the right place in the section.
  const totals = { total_areas: 11, submitted: 7, contacts_made: 40, ki: LAN_KI, trend: LAN_TREND };
  const summaries = { mission: {}, zones: { 'Zona Uno': totals }, districts: { 'Distrito Uno': {} } };
  const areas = { 'Área Uno': {
    zone: 'Zona Uno', district: 'Distrito Uno',
    stats: { submissions: 7, contacts_made: 40 },
    growth: null, strength1: null, strength2: null,
    ki: null, // keeps the MISSIONARY block silent so the matches below are the leader's
  } };
  const person = scope.a1c_buildPeopleMap([{
    Area_Name: 'Área Uno', Zone: 'Zona Uno', District: 'Distrito Uno',
    Companion1_Name: 'Elder Uno', Companion1_Email: LEADER_EMAIL,
    Companion2_Name: '', Companion2_Email: '',
    Is_ZL: 'TRUE', Is_DL: 'FALSE', Is_AP: 'FALSE', Is_STL: 'FALSE', Is_MP: 'FALSE', Active: 'TRUE',
  }])[LEADER_EMAIL];
  const letter = scope.a1c_buildEmail(person, areas, summaries, WEEK_END);

  const heading = letter.indexOf('Resumen de');
  const kiBlock = letter.indexOf('Indicadores Clave de la Zona');
  const trendB  = letter.indexOf('El Rumbo de la Zona');
  const tiles   = letter.indexOf('Reportaron');
  assert.ok(trendB !== -1, 'the trend block must reach the letter');
  assert.ok(heading < kiBlock && kiBlock < trendB && trendB < tiles,
    'where the unit IS, then where it is HEADING, then the nightly tiles');
  assert.ok(letter.includes('El Rumbo de la Zona') && !letter.includes('El Rumbo de la zona'),
    'the raw English scope token must never reach the letter');

  // (b) Through runAgent1A, which is where summaries.*.trend is produced.
  const { env: e2, scope: s2 } = loadScope(
    ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
     'CCSM_Agent3.gs', 'CCSM_Agent1A.gs']);
  const ss = makeCcsmSpreadsheet(e2, s2);
  setConfig(e2, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(e2, ss, 'TRANSFER_START_DATE', '2020-01-01');

  const today = new Date(); today.setHours(0, 0, 0, 0);
  const sunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
  const toStr = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') +
                       '-' + String(d.getDate()).padStart(2, '0');
  const weekEnd = toStr(sunday);
  const dayIn = (back) => toStr(new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() - back));

  addNightlyRaw(e2, ss, [
    { zone: 'Arauco', area: 'Arauco 1', report_date: weekEnd,  exchanges: 'No', effort: 'Todo', contacts_attempted: 20, contacts_made: 10 },
    { zone: 'Arauco', area: 'Arauco 1', report_date: dayIn(1), exchanges: 'No', effort: 'Todo', contacts_attempted: 20, contacts_made: 10 },
    { zone: 'Arauco', area: 'Arauco 1', report_date: dayIn(8), exchanges: 'No', effort: 'Algo', contacts_attempted: 30, contacts_made: 6 },
  ]);
  s2.runAgent3();
  s2.runAgent1A();

  const payload = s2.loadTempData('A1A_DATA');
  const zt = payload.summaries.zones['Arauco'].trend;
  assert.ok(zt && zt.weeks, 'runAgent1A must hang a trend roll-up on every zone summary');
  assert.strictEqual(zt.weeks.length, 4, 'four weeks, matching the four weekly bars');
  assert.strictEqual(zt.weeks[3].week, weekEnd, 'the last week carried is the week reported on');

  const cur = zt.weeks[3], prev = zt.weeks[2];
  assert.strictEqual(cur.days, 2, 'two nights this week');
  assert.strictEqual(prev.days, 1, 'one night the week before');
  assert.strictEqual(cur.metrics.contacts_attempted, 40);
  assert.strictEqual(prev.metrics.contacts_attempted, 30);
  assert.strictEqual(cur.metrics.contact_rate, 0.5, '20 / 40, from this unit\'s own sums');
  const districts = Object.keys(payload.summaries.districts);
  assert.ok(payload.summaries.mission.trend, 'the mission gets one too');
  assert.ok(districts.length > 0 && districts.every((d) => payload.summaries.districts[d].trend),
    'and so does every district');

  console.log('end-to-end wiring OK');
}

console.log('\ntest_rumbo_block: all checks passed');
