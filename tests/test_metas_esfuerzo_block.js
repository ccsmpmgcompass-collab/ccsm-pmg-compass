// test_metas_esfuerzo_block.js — "Las Metas y el Esfuerzo que las Sostiene",
// the third leadership block, plus the "Lectura de la semana" paragraph that
// replaced the standalone Gemini narrative box.
//
// WHY THIS EXISTS. The Key Indicators block says a zone reached 2 of 9
// baptismal dates. That sentence is unactionable on its own: a leader cannot
// tell whether the areas taught nobody or taught constantly and never invited.
// This block sets each meta beside the week of nightly work that was supposed
// to produce it, and the rules that make it honest are all rules the obvious
// version gets wrong:
//
//   - THE NUMBERS ARE RAW WEEKLY TOTALS, deliberately, even though the trend
//     block directly above is emphatically per reporting day. This block is
//     not a week-over-week comparison; it sets effort beside a meta that is
//     itself a weekly total, and dividing one side by days reported would
//     compare a rate against a count. The footnote states the basis rather
//     than leaving a reader to reconcile the two blocks.
//   - AN ARROW IS A CLAIM. "1.079 intentos → 459 contactos" says the second
//     number is a subset of the first. That is true only where a rate's own
//     num/den says it is, so the arrows are derived from A1A_RATE_METRICS
//     rather than typed in, and everything else is separated by a dot.
//   - A FEEDER WITH NO NUMBER IS OMITTED, NOT ZEROED. "0 Referencias
//     Solicitadas" says the areas asked for none; a mission whose nightly form
//     does not collect it has said nothing at all.
//   - AN INDICATOR THAT CANNOT BE PAIRED IS NAMED. The block above shows
//     seven rows and this one shows five; five rows with no explanation reads
//     as a rendering fault.
//
// It also locks in the removal of the standalone narrative box: the section
// carried two model-written paragraphs a few hundred pixels apart, and the
// old box rendered an unverified "📖 PMG p.N | escritura" line under one of
// them. Both prompts stopped asking for that citation here (the un-shipped
// half of tests/test_leadership_citations_withheld.js's scope), and
// a1c_narrativeProse_ strips a volunteered one rather than relocating it.
//
// The Los Angeles Norte week below is the live week the design was approved
// against; block 1 reproduces the approved table row for row.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet } = require('./fixtures');
const assert = require('assert');

const GS_FILES = ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
                  'CCSM_Agent3.gs', 'CCSM_Agent1A.gs', 'CCSM_SeedContent.gs', 'CCSM_Agent1C.gs'];

function loadScope() {
  const env = makeGasEnv();
  const scope = loadGs(GS_FILES, env.globals);
  makeCcsmSpreadsheet(env, scope); // a1c_buildEmail's footer calls getMissionName()
  scope.seedCcsmLeadershipMessageBank(); // section 10 renders the full letter, including the coaching card
  return { env, scope };
}

/**
 * A scope whose Gemini calls answer with `reply` and record their prompts.
 *
 * loadGs returns a SNAPSHOT of the declarations, so assigning scope.callGemini
 * afterwards rebinds nothing — the .gs code still calls its own. The stub has
 * to go in one layer lower, at the UrlFetchApp callGemini actually reaches,
 * which is also the only place the prompt text can be read back.
 */
function loadScopeWithGemini(reply) {
  const env = makeGasEnv();
  const prompts = [];
  env.globals.UrlFetchApp = {
    fetch(url, params) {
      prompts.push(JSON.parse(params.payload).contents[0].parts[0].text);
      return {
        getResponseCode: () => 200,
        getContentText: () => JSON.stringify(
          { candidates: [{ content: { parts: [{ text: reply }] } }] }),
      };
    },
  };
  const scope = loadGs(GS_FILES, env.globals);
  makeCcsmSpreadsheet(env, scope);
  scope.seedCcsmLeadershipMessageBank(); // section 10 renders the full letter, including the coaching card
  env.globals.PropertiesService.getScriptProperties().setProperty('GEMINI_API_KEY', 'test-key');
  return { env, scope, prompts };
}

// Agent1A rides along because A1A_KI_FEEDERS decides what feeds what and
// A1A_FRACTION_RATE_KEYS decides which pairs earn an arrow. The block reads
// both at render time rather than keeping a second copy, so a test that
// stubbed them would be testing the copy.
const { scope } = loadScope();

const GREEN = '#16a34a', BLUE = '#2563eb', YELLOW = '#a16207', RED = '#dc2626', MUTED = '#6b7280';
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

/** The three cells of every data row, in render order. */
function rowsOf(html) {
  const re = new RegExp(
    '<td style="padding:6px 4px;[^"]*color:#374151;">([^<]*)</td>' +
    '<td style="[^"]*color:(#[0-9a-f]{6});">([^<]*)</td>' +
    '<td style="[^"]*">(.*?)</td>', 'g');
  const out = [];
  let m;
  while ((m = re.exec(html)) !== null) {
    out.push({ display: m[1], color: m[2], ratio: m[3], effort: m[4] });
  }
  return out;
}

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
function ki(pairs, over) {
  const defs = KI_DEFS.slice(0, pairs.length);
  return Object.assign({
    metaWeekEnd: '2026-08-16', areasTotal: 11, areasReported: 7,
    fallbackAreas: [], silentAreas: [],
    metasSet: pairs.filter((p) => p[1] > 0).length,
    metasAchieved: pairs.filter((p) => p[1] > 0 && p[0] >= p[1]).length,
    indicators: defs.map((d, i) => ({
      key: d[0], display: d[1], real: pairs[i][0], meta: pairs[i][1],
      achieved: pairs[i][1] > 0 && pairs[i][0] >= pairs[i][1],
    })),
  }, over || {});
}

// ── The real Los Angeles Norte week (2026-08-17 → 23), from the live sheet ──
// 4 of 7 metas met; the weakest indicator with a nightly chain is
// "Amigos con Fecha Bautismal" at 2 of 9, which is what the trend block above
// features and what this table has to finish on.
const LAN_KI = ki([[78, 75], [52, 52], [20, 20], [1, 1], [2, 9], [0, 0], [16, 25]]);

const LAN_STATS = {
  contacts_attempted: 1079, contacts_made: 459, meaningful_conversations: 263,
  member_contacts: 272, lessons_member_present: 58, references_asked: 18,
  church_invites: 167, rc_lessons: 17,
  baptism_doctrine_lessons: 39, baptismal_invitations: 12, baptismal_calendars: 5,
};
const LAN_TOTALS = Object.assign({ total_areas: 11, submitted: 7, ki: LAN_KI }, LAN_STATS);

const PROSE = 'La zona encuentra gente de sobra y se detiene más adelante.';
const block = (k, totals, prose) =>
  scope.a1c_buildMetasEsfuerzoBlock_(k, totals, prose === undefined ? PROSE : prose, C);

// ===========================================================================
// 1. The approved table, row for row: Los Angeles Norte's real week.
//    Metas met first, then closest-to-met, so the row a leader finishes on is
//    the one the trend block above just explained.
// ===========================================================================
{
  const html = block(LAN_KI, LAN_TOTALS);
  const rows = rowsOf(html);

  assert.strictEqual(rows.length, 5,
    'five of the seven indicators have a nightly chain behind them');
  assert.deepStrictEqual(rows.map((r) => r.display), [
    'Nuevas Personas Encontradas',
    'Lecciones con Miembros',
    'Amigos en la Reunión Sacramental',
    'Conversos Recientes en la Iglesia',
    'Amigos con Fecha Bautismal',
  ], 'metas met first, then by share of the meta reached — the weakest last');
  assert.deepStrictEqual(rows.map((r) => r.ratio),
    ['78/75', '52/52', '20/20', '16/25', '2/9']);

  // The colour authority is a1c_goalBandColor_, the same call the Key
  // Indicator tiles make. A fixed colour would give a zone that met nothing
  // the same row as one that met everything.
  assert.deepStrictEqual(rows.map((r) => r.color), [GREEN, GREEN, GREEN, BLUE, YELLOW],
    '104% / 100% / 100% green, 64% blue, 22% yellow');

  assert.ok(html.includes('📊 Las Metas y el Esfuerzo que las Sostiene'), 'the block title');
  console.log('approved Los Angeles Norte table reproduced OK');
}

// ===========================================================================
// 2. Raw weekly totals in Spanish notation, and arrows only where a rate's
//    own num/den says the second number is a subset of the first.
// ===========================================================================
{
  const rows = rowsOf(block(LAN_KI, LAN_TOTALS));
  const byName = {};
  rows.forEach((r) => { byName[r.display] = r.effort; });

  assert.strictEqual(byName['Nuevas Personas Encontradas'],
    '1.079 Intentos de Contacto → 459 Contactos → 263 Conversaciones Significativas',
    'contact_rate and mc_rate are literally made of these three, so both arrows are earned');

  // 1079 / 45 reported days = 23,98. The trend block above divides; this one
  // must not, because the meta it sits beside is a weekly total.
  const all = rows.map((r) => r.effort).join(' ');
  assert.ok(all.includes('1.079'), 'four-digit counts carry the Spanish thousands separator');
  assert.ok(!/23,9|24,0/.test(all), 'per-reporting-day averages belong to the trend block, not here');

  assert.strictEqual(byName['Lecciones con Miembros'],
    '272 Contactos con Miembros · 58 Lecciones con Miembro Presente · 18 Referencias Solicitadas',
    'these are parallel efforts; an arrow would claim a funnel that does not exist');
  assert.ok(!byName['Lecciones con Miembros'].includes('→'));
  assert.ok(!byName['Amigos con Fecha Bautismal'].includes('→'),
    'baptism_doctrine_lessons is not close_rate\'s denominator — friend_lessons is');

  // Labels are a1c_scoreboardLabel_'s, i.e. the nightly form's own wording,
  // so the same metric is not called two things in one letter.
  assert.strictEqual(scope.a1c_scoreboardLabel_('baptismal_calendars'),
    'Calendarios Bautismales Entregados');
  assert.ok(byName['Amigos con Fecha Bautismal'].includes('5 Calendarios Bautismales Entregados'));

  const foot = textOf(block(LAN_KI, LAN_TOTALS));
  assert.ok(foot.includes('totales de la semana, no promedios por día informado'),
    'the basis is stated, not left to be inferred against the block above');
  console.log('raw weekly totals, Spanish integers and earned arrows OK');
}

// ===========================================================================
// 3. A feeder this mission's nightly form does not collect is left out — not
//    printed as 0 — and it breaks the arrow chain rather than letting the two
//    numbers either side inherit an arrow they never earned.
// ===========================================================================
{
  const totals = Object.assign({}, LAN_TOTALS);
  delete totals.contacts_made;
  const byName = {};
  rowsOf(block(LAN_KI, totals)).forEach((r) => { byName[r.display] = r.effort; });

  assert.strictEqual(byName['Nuevas Personas Encontradas'],
    '1.079 Intentos de Contacto · 263 Conversaciones Significativas',
    'the missing middle breaks the chain: mc_rate\'s denominator is not on the row');
  assert.ok(!/0 Contactos/.test(byName['Nuevas Personas Encontradas']),
    '"0 Contactos" claims the areas made none, which is a different fact');
  console.log('uncollected feeders omitted, not zeroed OK');
}

// ===========================================================================
// 4. An indicator with no nightly chain is NAMED. Singular and plural both
//    have to read as Spanish.
// ===========================================================================
{
  const plural = textOf(block(LAN_KI, LAN_TOTALS));
  assert.ok(plural.includes(
    'Amigos en la Iglesia (Primera Semana) y Bautizados y Confirmados no aparecen aquí'),
    'both chainless indicators are named, joined with "y"');
  assert.ok(plural.includes('no registra números que los alimenten.'));

  // The first four indicators only: of those, ki_friends_first_week alone has
  // no nightly chain.
  const four = ki([[78, 75], [52, 52], [20, 20], [1, 1]]);
  const singular = textOf(block(four, Object.assign({}, LAN_TOTALS, { ki: four })));
  assert.ok(singular.includes('Amigos en la Iglesia (Primera Semana) no aparece aquí'),
    'the naive version prints "no aparecen" for one indicator');
  assert.ok(singular.includes('no registra un número que lo alimente.'));
  assert.strictEqual(rowsOf(block(four, LAN_TOTALS)).length, 3);
  console.log('chainless indicators named, singular and plural OK');
}

// ===========================================================================
// 5. The two blocks agree. This table's order must be the Key Indicator
//    block's order with the unpairable rows removed — a leader reading down
//    the letter should not meet the same seven indicators twice in two
//    different orders.
// ===========================================================================
{
  const kiHtml = scope.a1c_buildLeaderKiBlock_(LAN_KI, 'zone', C);
  const kiOrder = [];
  const re = /<div style="font-size:11px;font-weight:700;color:#374151;margin-bottom:3px;">([^<]*)<\/div>/g;
  let m;
  while ((m = re.exec(kiHtml)) !== null) kiOrder.push(m[1]);
  assert.strictEqual(kiOrder.length, 7, 'the block above shows all seven');

  const tableOrder = rowsOf(block(LAN_KI, LAN_TOTALS)).map((r) => r.display);
  assert.deepStrictEqual(tableOrder, kiOrder.filter((d) => tableOrder.indexOf(d) !== -1),
    'same sort, same order, one subset of the other');
  console.log('order agrees with the Key Indicator block OK');
}

// ===========================================================================
// 6. Nothing filed anywhere in the unit: the Key Indicator block above already
//    says the week is missing. Five rows of "0/—" against zero effort would
//    say it a second time and worse. The Lectura paragraph still renders —
//    a missing WEEKLY_KI is no reason to withhold the week's reading.
// ===========================================================================
{
  // The nightly numbers are real and present: an area can send its nightly
  // report all week and still never file the weekly indicator form, which is
  // what makes this the interesting case rather than an empty one.
  const silentKi = ki([[0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
    { areasReported: 0, metasSet: 0, metasAchieved: 0 });
  const silentTotals = Object.assign({ total_areas: 3, submitted: 3, ki: silentKi }, LAN_STATS);
  assert.ok(rowsOf(block(ki([[0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]),
    silentTotals)).length > 0, 'the same numbers DO render when an area filed');
  const html = block(silentKi, silentTotals);

  assert.strictEqual(rowsOf(html).length, 0, 'no rows');
  assert.ok(!html.includes('Las Metas y el Esfuerzo que las Sostiene'),
    'no heading over an empty table');
  assert.ok(html.includes('Lectura de la semana') && html.includes(PROSE),
    'the reading of the week survives a unit that filed nothing');

  // Same rule when WEEKLY_KI itself was unreadable.
  assert.ok(block(null, {}).includes('Lectura de la semana'));
  assert.strictEqual(block(null, {}, ''), '', 'nothing to say at all renders nothing');
  console.log('silent unit and unreadable WEEKLY_KI OK');
}

// ===========================================================================
// 7. The Lectura box, and the disclosure that goes with it. Leaders are the
//    only people in this mission who receive model-written text; the letter
//    has to say which paragraph that is.
// ===========================================================================
{
  const html = block(LAN_KI, LAN_TOTALS);
  assert.ok(html.includes('>GEMINI<'), 'the badge names the writer');
  assert.ok(html.includes('border-left:4px solid ' + C.blue), 'the approved blue rule');
  const t = textOf(html);
  assert.ok(t.includes('Este párrafo lo redacta un modelo de lenguaje'));
  assert.ok(t.includes('las cartas de los misioneros no llevan texto generado por inteligencia artificial'),
    'the missionary letters carry no AI text at all — say so where the AI text is');

  const noProse = block(LAN_KI, LAN_TOTALS, '');
  assert.ok(!noProse.includes('Lectura de la semana'), 'no box when Gemini returned nothing');
  assert.ok(!noProse.includes('GEMINI'), 'and no orphan badge');
  assert.ok(rowsOf(noProse).length === 5, 'the table does not depend on the paragraph');
  console.log('Lectura box and AI disclosure OK');
}

// ===========================================================================
// 8. a1c_narrativeProse_: the two belt-and-suspenders filters. Neither is the
//    primary defence — both prompts forbid these outright — but both failure
//    modes reach a real reader if a model ignores its prompt.
// ===========================================================================
{
  const raw = 'Los investigadores de la zona avanzan y un investigador se bautizó.\n' +
              'PMG p.157 | D. y C. 4:4-5';
  const out = scope.a1c_narrativeProse_(raw);

  assert.ok(!/investigador/i.test(out), 'the mission says "amigos"');
  assert.ok(out.includes('Los amigos de la zona') && out.includes('un amigo se bautizó'),
    'singular and plural both replaced');
  assert.ok(!/PMG p\./i.test(out) && !out.includes('D. y C. 4:4-5'),
    'a volunteered citation is stripped AND discarded, never relocated under a 📖 glyph');
  assert.strictEqual(scope.a1c_narrativeProse_('PMG p.157 | D. y C. 4:4-5'), '',
    'a response that is nothing but a citation leaves no paragraph');
  assert.strictEqual(scope.a1c_narrativeProse_(''), '');

  // Prose still goes through a1c_esc — this text lands inside an HTML box.
  assert.ok(scope.a1c_narrativeProse_('Subió 5 < 6 & bajó').includes('&lt;'));
  console.log('narrative prose filters OK');
}

// ===========================================================================
// 9. BOTH prompts. Every unit except the mission takes the batch path, so a
//    rule fixed only in the per-unit prompt leaves 20 of the 21 leadership
//    letters on the old wording — which is exactly how the citation
//    instruction survived its first removal.
// ===========================================================================
{
  const { scope: s, prompts } = loadScopeWithGemini(PROSE);

  s.a1c_buildLeadershipNarrative('zone', 'Zona Uno', LAN_TOTALS, [], WEEK_END);
  s.a1c_fetchBatchNarratives_('zone', { 'Zona Uno': LAN_TOTALS }, {}, WEEK_END);

  assert.strictEqual(prompts.length, 2, 'one per-unit prompt and one batch prompt');
  prompts.forEach((p, i) => {
    const which = i === 0 ? 'per-unit' : 'batch';
    const BAN = 'NO incluya referencias de páginas, citas de libros ni referencias de escrituras. ' +
                'Escriba solo el párrafo.';
    assert.ok(p.includes(BAN), which + ': must forbid citations outright');
    // Everything except that one rule: the prompt must not mention a page
    // reference or a scripture anywhere else, which is how the old
    // "Línea 2: PMG p.{página} | {escritura}" format spec used to survive.
    const rest = p.split(BAN).join('');
    assert.ok(!/PMG/i.test(rest), which + ': must not ask for a Predicad Mi Evangelio page');
    assert.ok(!/escritura/i.test(rest), which + ': must not ask for a scripture reference');
    assert.ok(p.includes('Lectura de la semana'), which + ': must ask for the Lectura paragraph');
    // The paragraph has to read the table the leader is looking at, so both
    // prompts are fed the same pairing the table renders.
    assert.ok(p.includes('Metas de la semana pasada y el esfuerzo nocturno que las sostuvo'),
      which + ': must carry the metas/effort pairing');
    assert.ok(p.includes('Amigos con Fecha Bautismal: 2 contra una meta de 9'),
      which + ': the pairing must carry real numbers');
    assert.ok(p.includes('39 Lecciones de Doctrina del Bautismo'),
      which + ': and the effort behind them');
    assert.ok(!/\binvestigador/i.test(p.replace(/NUNCA use la palabra "investigador"[^\n]*/g, '')),
      which + ': the only mention of "investigador" is the rule forbidding it');
  });
  console.log('both Gemini prompts rewritten OK');
}

// ===========================================================================
// 10. End to end. Every check above can pass with the call site unwired, and
//     the standalone narrative box removed here is the reason the section
//     stopped carrying two model-written paragraphs.
// ===========================================================================
{
  const { scope: s } = loadScopeWithGemini(PROSE);

  const totals = Object.assign({}, LAN_TOTALS);
  const summaries = { mission: {}, zones: { 'Zona Uno': totals }, districts: { 'Distrito Uno': {} } };
  const areas = { 'Área Uno': {
    zone: 'Zona Uno', district: 'Distrito Uno',
    stats: { submissions: 7, contacts_made: 40 },
    growth: null, strength1: null, strength2: null,
    ki: null, // keeps the MISSIONARY block silent so the matches below are the leader's
  } };
  const person = s.a1c_buildPeopleMap([{
    Area_Name: 'Área Uno', Zone: 'Zona Uno', District: 'Distrito Uno',
    Companion1_Name: 'Elder Uno', Companion1_Email: LEADER_EMAIL,
    Companion2_Name: '', Companion2_Email: '',
    Is_ZL: 'TRUE', Is_DL: 'FALSE', Is_AP: 'FALSE', Is_STL: 'FALSE', Is_MP: 'FALSE', Active: 'TRUE',
  }])[LEADER_EMAIL];
  const letter = s.a1c_buildEmail(person, areas, summaries, WEEK_END);

  const heading = letter.indexOf('Resumen de');
  const kiBlock = letter.indexOf('Indicadores Clave de la Zona');
  const metas   = letter.indexOf('Las Metas y el Esfuerzo que las Sostiene');
  const tiles   = letter.indexOf('Reportaron');
  assert.ok(metas !== -1, 'the block must reach the letter');
  assert.ok(heading < kiBlock && kiBlock < metas && metas < tiles,
    'where the unit IS, then where it is HEADING, then the metas, then the nightly tiles');
  assert.ok(letter.includes(PROSE), 'and the paragraph with it');

  // The old grey box is gone: its rounded-corner rule, its 📖 citation line,
  // and its heading, which now belongs to exactly one thing in the letter.
  assert.ok(!letter.includes('border-radius:0 6px 6px 0'),
    'the standalone narrative box must not render');
  assert.ok(!/📖 PMG/.test(letter));
  assert.strictEqual(letter.split('Capacitación de Líderes').length - 1, 1,
    'only the static coaching card at the foot of the section carries that name now');
  console.log('call site, order and the removed narrative box OK');
}

console.log('\ntest_metas_esfuerzo_block: all blocks passed');
