// test_ki_prior_week_metas.js — the missionary "Indicadores Clave" block now
// grades this week's results against LAST week's metas
// (Agent1A area.kiMetaPrev -> Agent1C a1c_buildKiBlock_).
//
// WHY THIS EXISTS. A meta on a WEEKLY_KI row is not a goal for that row's
// week — it is next week's plan. The weekly form tells the missionary so in
// as many words: the metas are "las metas que usted estableció durante la
// planificación semanal para la semana siguiente" (WeeklyReportForm_ES.gs:117).
// Reading real and meta off the same row therefore graded every companionship
// in the mission against a goal it had not started working on. It is not a
// rounding-level difference: the two metas agree for only about half of the
// area-by-indicator pairs, and whole verdicts flip.
//
// Each assertion below guards a place where a plausible-looking number would
// mislead the reader:
//   - The pair, the percentage, the bar colour and the "Meta alcanzada"
//     verdict all have to come from the PRIOR week's meta, not just the
//     caption. Fixing the wording alone would leave the grade wrong.
//   - A companionship that filed nothing last week has no prior meta, so it
//     falls back to its own same-week meta. That fallback is DATED and
//     daggered — a comparison whose basis silently changes between letters is
//     worse than either basis alone.
//   - A prior meta of 0 must read as "no fijaron meta", not quietly borrow
//     this week's meta. Per-row borrowing would make the block's basis
//     unknowable row by row.
//   - The empty and unavailable states are untouched: a missing report still
//     says so, and an unreadable source still renders nothing at all.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const env = makeGasEnv();
const scope = loadGs(
  ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_Agent1C.gs'],
  env.globals);
// a1c_formatDate reads the mission timezone out of AGENT_CONFIG.
makeCcsmSpreadsheet(env, scope);

const GREEN = '#16a34a', BLUE = '#2563eb', YELLOW = '#a16207', RED = '#dc2626', MUTED = '#6b7280';

const C = {
  header: '#1e3a5f', green: GREEN, blue: BLUE, yellow: YELLOW, red: RED,
  muted: MUTED, border: '#e5e7eb', bgLight: '#f9fafb',
};

const KI_KEYS = [
  'ki_new_people', 'ki_member_lessons', 'ki_friends_sacrament',
  'ki_friends_first_week', 'ki_baptismal_date', 'ki_baptized_confirmed',
  'ki_rc_at_church',
];
const KI_DISPLAYS = [
  'Nuevas Personas Encontradas', 'Lecciones con Miembros',
  'Amigos en la Reunión Sacramental', 'Amigos en la Iglesia (Primera Semana)',
  'Amigos con Fecha Bautismal', 'Bautizados y Confirmados',
  'Conversos Recientes en la Iglesia',
];

const WEEK_END = '2026-08-23';
const PREV_END = '2026-08-16';
const PREV_LABEL = '16 de agosto';
const THIS_LABEL = '23 de agosto';

/** area.ki in the shape a1a_loadWeeklyKi returns. `pairs` is [real, sameWeekMeta] per indicator. */
function kiArray(pairs) {
  return KI_KEYS.map((key, i) => ({
    key: key, display: KI_DISPLAYS[i], real: pairs[i][0], meta: pairs[i][1],
  }));
}
/** area.kiMetaPrev in the shape a1a_kiMetaMap_ returns. */
function metaMap(metas) {
  const out = {};
  KI_KEYS.forEach((key, i) => { out[key] = metas[i]; });
  return out;
}
/** The block's text, tags stripped — for prose assertions that ignore markup. */
function textOf(html) {
  return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
}
/** The caption under a rendered pair, e.g. "64% de la meta". */
function captionAfter(html, pair) {
  const at = html.indexOf('>' + pair + '</td>');
  assert.ok(at > 0, 'expected the pair "' + pair + '" to render');
  const m = html.slice(at).match(/margin-top:2px;">(.*?)<\/div>/);
  return m ? textOf(m[1]).trim() : null;
}
/** The bar/pair colour on a rendered pair. */
function colorOf(html, pair) {
  const at = html.indexOf('>' + pair + '</td>');
  assert.ok(at > 0, 'expected the pair "' + pair + '" to render');
  const m = html.slice(0, at).match(/color:(#[0-9a-fA-F]{6});font-size:11px;"$/);
  return m ? m[1].toLowerCase() : null;
}

// ===========================================================================
// 1. a1c_prevWeekEnd_ — seven days back, across the boundaries that a naive
//    string edit or a milliseconds subtraction gets wrong.
// ===========================================================================
{
  assert.strictEqual(scope.a1c_prevWeekEnd_('2026-08-23'), '2026-08-16');
  assert.strictEqual(scope.a1c_prevWeekEnd_('2026-09-06'), '2026-08-30', 'must cross a month boundary');
  assert.strictEqual(scope.a1c_prevWeekEnd_('2026-01-03'), '2025-12-27', 'must cross a year boundary');
  assert.strictEqual(scope.a1c_prevWeekEnd_('2028-03-05'), '2028-02-27', 'must cross a leap February');
  // A Sunday must stay a Sunday, which a DST-crossing millisecond subtraction
  // would not guarantee. Chile changes clocks in September and April.
  ['2026-04-05', '2026-04-12', '2026-09-06', '2026-09-13'].forEach((wk) => {
    const p = scope.a1c_prevWeekEnd_(wk).split('-').map(Number);
    assert.strictEqual(new Date(p[0], p[1] - 1, p[2]).getDay(), 0,
      wk + ' must land on a Sunday, not slip a day across a clock change');
  });
  ['', null, undefined, 'la semana pasada'].forEach((junk) => {
    assert.strictEqual(scope.a1c_prevWeekEnd_(junk), '', 'a non-date must yield an empty string');
  });

  console.log('prev week-end arithmetic OK');
}

// ===========================================================================
// 2. The prior week's meta is the one graded against — pair, percentage,
//    colour and verdict, not just the caption.
// ===========================================================================
{
  //                real, this-week meta        prior-week meta
  const ki = kiArray([[8, 10], [16, 16], [2, 2], [1, 1], [2, 2], [0, 0], [3, 3]]);
  const prev = metaMap([8, 25, 4, 2, 9, 0, 3]);
  const html = scope.a1c_buildKiBlock_(ki, C, WEEK_END, prev);
  const text = textOf(html);

  // Every pair takes its denominator from `prev`.
  assert.ok(html.includes('>8 / 8</td>'),   'the prior meta 8 must be the denominator, not this week\'s 10');
  assert.ok(html.includes('>16 / 25</td>'), 'the prior meta 25 must be the denominator, not this week\'s 16');
  assert.ok(html.includes('>2 / 9</td>'),   'the prior meta 9 must be the denominator, not this week\'s 2');
  assert.ok(!html.includes('>8 / 10</td>'), 'this week\'s own meta must not be paired with this week\'s result');
  assert.ok(!html.includes('>16 / 16</td>'), 'a same-row pair must not survive anywhere in the block');

  // The verdict flips with it — 8 against 10 is 80%, 8 against 8 is met.
  assert.strictEqual(captionAfter(html, '8 / 8'), 'Meta alcanzada ✓',
    'a goal met against the prior meta must read as met');
  assert.strictEqual(colorOf(html, '8 / 8'), GREEN, 'a met goal is green');
  assert.strictEqual(captionAfter(html, '16 / 25'), '64% de la meta',
    'the percentage must be computed from the prior meta');
  assert.strictEqual(colorOf(html, '16 / 25'), BLUE, '64% lands in the blue band');
  assert.strictEqual(captionAfter(html, '2 / 9'), '22% de la meta');
  assert.strictEqual(colorOf(html, '2 / 9'), YELLOW, '22% lands in the yellow band');

  // And the caption dates the metas at the week they were filed.
  assert.ok(text.includes('metas que ustedes fijaron el ' + PREV_LABEL),
    'the sub-caption must date the metas at the prior week-end, got: ' + text.slice(0, 220));
  assert.ok(!text.includes('fijaron el ' + THIS_LABEL),
    'the sub-caption must never date the metas at the week being reported');

  // Nothing was borrowed, so nothing is daggered.
  assert.ok(!html.includes('†'), 'no dagger when every meta came from the prior week');
  assert.ok(!text.includes('No recibimos su informe semanal de la semana anterior'),
    'no fallback footnote when there was nothing to fall back from');

  console.log('prior-week metas grade the block OK');
}

// ===========================================================================
// 3. A prior meta of 0 reads as "no fijaron meta" — it must NOT quietly
//    borrow this week's meta for that one row. Per-row borrowing would make
//    the block's basis unknowable line by line.
// ===========================================================================
{
  const ki = kiArray([[5, 5], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]);
  const prev = metaMap([0, 0, 0, 0, 0, 0, 0]);
  const html = scope.a1c_buildKiBlock_(ki, C, WEEK_END, prev);

  assert.ok(html.includes('>5 / —</td>'),
    'an indicator with no prior meta must render a dash, never this week\'s meta');
  assert.ok(!html.includes('>5 / 5</td>'), 'this week\'s meta must not fill in for a prior meta of 0');
  assert.ok(html.includes('no fijaron meta para este indicador'),
    'a zero prior meta must say the meta was never set');
  assert.ok(!html.includes('sin meta esta semana'),
    '"esta semana" is the wrong week once the block reads prior metas');
  assert.ok(!/color:#dc2626;">no fijaron meta/.test(html), 'an unset meta takes no band colour');
  assert.ok(!html.includes('†'), 'a zero prior meta is not a fallback — the map was there');

  console.log('zero prior meta reads as unset OK');
}

// ===========================================================================
// 4. No prior report at all -> fall back to this week's meta, dated and
//    daggered. This is the one case where the basis changes, and the letter
//    has to say so out loud.
// ===========================================================================
{
  const ki = kiArray([[8, 10], [16, 16], [2, 2], [1, 1], [2, 2], [0, 0], [3, 3]]);

  [null, undefined].forEach((absent) => {
    const html = scope.a1c_buildKiBlock_(ki, C, WEEK_END, absent);
    const text = textOf(html);

    assert.ok(html.includes('>8 / 10</td>'), 'with no prior meta the same-week meta is used');
    assert.ok(html.includes('>16 / 16</td>'), 'every row falls back together, not just some');
    assert.strictEqual(captionAfter(html, '8 / 10'), '80% de la meta',
      'the fallback percentage comes from this week\'s meta');

    assert.ok(text.includes('metas que ustedes fijaron en el informe de esta misma semana'),
      'the sub-caption must name which week the metas came from');
    assert.ok(html.includes('†'), 'the fallback must be daggered');
    assert.ok(text.includes('No recibimos su informe semanal de la semana anterior'),
      'the footnote must say why the basis changed');
    assert.ok(text.includes('la que terminó el ' + PREV_LABEL),
      'the footnote must date the missing week, got: ' + text.slice(-400));
    assert.ok(text.includes('Normalmente usa las metas de la semana anterior'),
      'the footnote must state what the normal basis is, or the dagger explains nothing');

    // The old wording belongs to the fallback path only.
    assert.ok(html.includes('sin meta esta semana'),
      'on the fallback path an unset meta really is this week\'s');
    assert.ok(!html.includes('no fijaron meta para este indicador'),
      'the prior-week wording must not leak onto the fallback path');
  });

  console.log('fallback to same-week metas is dated and daggered OK');
}

// ===========================================================================
// 5. A weekEnd that is not a date still renders — the block degrades to
//    "la semana pasada" rather than printing a broken date or throwing.
// ===========================================================================
{
  const ki = kiArray([[8, 10], [1, 1], [1, 1], [1, 1], [1, 1], [1, 1], [1, 1]]);
  const text = textOf(scope.a1c_buildKiBlock_(ki, C, '', metaMap([8, 1, 1, 1, 1, 1, 1])));
  assert.ok(text.includes('metas que ustedes fijaron la semana pasada'),
    'an unusable weekEnd falls back to a relative phrase');
  assert.ok(!/fijaron el\b/.test(text), 'no half-built date may render');

  const fb = textOf(scope.a1c_buildKiBlock_(ki, C, '', null));
  assert.ok(fb.includes('No recibimos su informe semanal de la semana anterior,'),
    'the footnote drops the date clause rather than printing an empty one');
  assert.ok(!fb.includes('la que terminó'), 'no dangling "la que terminó" without a date');

  console.log('undated weekEnd degrades cleanly OK');
}

// ===========================================================================
// 6. The empty and unavailable states are untouched by any of this. Neither
//    may grow a meta caption: there are no results to date.
// ===========================================================================
{
  [null, undefined].forEach((absent) => {
    assert.strictEqual(scope.a1c_buildKiBlock_(absent, C, WEEK_END, metaMap([1, 1, 1, 1, 1, 1, 1])), '',
      'an unreadable source renders nothing, prior metas or not');
  });

  [metaMap([1, 1, 1, 1, 1, 1, 1]), null].forEach((prev) => {
    const html = scope.a1c_buildKiBlock_([], C, WEEK_END, prev);
    assert.ok(html.includes('No recibimos su informe semanal de indicadores clave'),
      'a missing weekly report is still stated plainly');
    assert.ok(!html.includes('metas que ustedes fijaron el'),
      'a letter with no results must not caption a comparison it cannot make');
    assert.ok(!html.includes('†'), 'nothing to dagger when nothing was reported');
    assert.ok(!html.includes(' / '), 'a missing report must never render pairs');
  });

  console.log('empty and unavailable states unchanged OK');
}

// ===========================================================================
// 7. End to end. Two WEEKLY_KI rows through the real chain: only wiring
//    area.kiMetaPrev to the block makes this pass, and it is the one thing
//    the direct-render blocks above cannot check.
// ===========================================================================
{
  function toDateStr(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  const chainEnv = makeGasEnv();
  const chainScope = loadGs(
    ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
      'CCSM_Agent3.gs', 'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs'],
    chainEnv.globals);
  const ss = makeCcsmSpreadsheet(chainEnv, chainScope);
  setConfig(chainEnv, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(chainEnv, ss, 'TRANSFER_START_DATE', '2020-01-01');

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const thisSunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
  const weekEnd = toDateStr(thisSunday);
  const prevEnd = toDateStr(new Date(thisSunday.getFullYear(), thisSunday.getMonth(), thisSunday.getDate() - 7));

  const days = [];
  for (let i = 6; i >= 0; i--) {
    days.push(toDateStr(new Date(thisSunday.getFullYear(), thisSunday.getMonth(), thisSunday.getDate() - i)));
  }
  addNightlyRaw(chainEnv, ss, days.map((d, i) => ({
    zone: 'Arauco', area: 'Arauco 1', report_date: d, exchanges: 'Sí', effort: 'Algo',
    ...(i === 0 ? {
      contacts_attempted: 30, contacts_made: 15,
      meaningful_conversations: 10, friend_lessons: 20, baptismal_invitations: 1,
    } : {}),
  })));
  chainScope.runAgent3();

  const headers = ['Week_End_Date', 'Area', 'Zone', 'District']
    .concat(...KI_KEYS.map((k) => [k + '_real', k + '_meta']))
    .concat(['leader_call', 'correlation_meeting']);
  const sheet = ss.insertSheet('WEEKLY_KI');
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  [
    // Last week: results nobody reads any more, and the metas for THIS week.
    { Week_End_Date: prevEnd, Area: 'Arauco 1', Zone: 'Arauco', District: 'Arauco',
      ki_new_people_real: 99, ki_new_people_meta: 12,
      ki_member_lessons_real: 99, ki_member_lessons_meta: 25 },
    // This week: the results, beside metas that belong to NEXT week.
    { Week_End_Date: weekEnd, Area: 'Arauco 1', Zone: 'Arauco', District: 'Arauco',
      ki_new_people_real: 12, ki_new_people_meta: 40,
      ki_member_lessons_real: 16, ki_member_lessons_meta: 16 },
  ].forEach((row) => {
    sheet.appendRow(headers.map((h) => (row[h] !== undefined ? row[h] : '')));
  });

  const orgSheet = ss.getSheetByName('MISSION_ORG');
  const orgData = orgSheet.getDataRange().getValues();
  const areaCol = orgData[0].indexOf('Area_Name');
  const emailCol = orgData[0].indexOf('Companion1_Email');
  for (let i = 1; i < orgData.length; i++) {
    if (orgData[i][areaCol] === 'Arauco 1') {
      orgSheet.getRange(i + 1, emailCol + 1).setValue('arauco1@example.com');
      break;
    }
  }
  const bank = ss.getSheetByName('MESSAGE_BANK');
  bank.appendRow(['S-LR-001', 'SUNDAY_COACHING_STRENGTH', 'lesson_rate', '', '¡Excelente!', 'Cuerpo.', '174', 'Enseñar', 'Alma 26:22', '', 'TRUE']);
  bank.appendRow(['G-CL-001', 'SUNDAY_COACHING_GROWTH', 'close_rate', '', 'Oportunidad', 'Cuerpo.', '205', 'Invitar', 'Moroni 10:4', '', 'TRUE']);

  chainScope.runAgent1A();
  chainScope.runAgent1B();
  chainScope.runAgent1C();

  const email = chainEnv.state.emails.find((e) => e.to === 'CCSM.PMG.Compass@gmail.com');
  assert.ok(email, 'expected an email captured to the TEST_MODE inbox');
  const body = email.htmlBody || '';

  assert.ok(body.includes('>12 / 12</td>'),
    'the letter must pair this week\'s 12 with last week\'s meta of 12');
  assert.ok(body.includes('>16 / 25</td>'),
    'the letter must pair this week\'s 16 with last week\'s meta of 25');
  assert.ok(!body.includes('>12 / 40</td>'),
    'this week\'s meta of 40 belongs to next week and must not be graded now');
  assert.ok(!body.includes('>16 / 16</td>'), 'no same-row pair may reach the letter');
  assert.ok(!body.includes('>99 / '), 'last week\'s results must not be re-reported');
  assert.ok(!body.includes('†'), 'this area filed both weeks — nothing to dagger');

  console.log('end-to-end prior-week wiring OK');
}

console.log('ki prior week metas OK');
