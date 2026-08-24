// test_agent1c_key_indicators.js — the weekly Key Indicators block that now
// leads the coaching letter (Agent1A a1a_loadWeeklyKi -> area.ki -> Agent1C
// a1c_buildKiBlock_).
//
// These 7 indicators come from the WEEKLY form, not the nightly one, so they
// are the only numbers in the letter measured against the companionship's OWN
// meta. Three of them have no nightly equivalent at all, which is why the
// letter could say nothing about them before this block existed.
//
// Covers the three states the block distinguishes, because conflating them is
// the easy bug: real numbers, "you filed no weekly report", and "the source
// itself is unavailable" (which must NOT blame the companionship).
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const geminiEnvelope = JSON.stringify({
  candidates: [{ content: { parts: [{ text: JSON.stringify({ Arauco: 'Narrativa de prueba.' }) }] } }],
});
const geminiResponse = { getResponseCode: () => 200, getContentText: () => geminiEnvelope };

const KI_KEYS = [
  'ki_new_people', 'ki_member_lessons', 'ki_friends_sacrament',
  'ki_friends_first_week', 'ki_baptismal_date', 'ki_baptized_confirmed',
  'ki_rc_at_church',
];

function toDateStr(d) {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
function weekDatesEnding(sunday) {
  const out = [];
  for (let i = 6; i >= 0; i--) out.push(toDateStr(new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() - i)));
  return out;
}

// Builds a chain run and returns the TEST_MODE email body. `kiRows` is either
// null (do not create WEEKLY_KI at all) or an array of row objects.
function runChain(kiRows) {
  const env = makeGasEnv({ geminiResponse });
  const scope = loadGs(
    ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_Agent3.gs', 'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs'],
    env.globals
  );
  const ss = makeCcsmSpreadsheet(env, scope);
  setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const thisSunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
  const weekEnd = toDateStr(thisSunday);

  addNightlyRaw(env, ss, weekDatesEnding(thisSunday).map((d, i) => ({
    zone: 'Arauco', area: 'Arauco 1', report_date: d, exchanges: 'Sí', effort: 'Algo',
    ...(i === 0 ? {
      contacts_attempted: 30, contacts_made: 15,
      meaningful_conversations: 10, friend_lessons: 20, baptismal_invitations: 1,
    } : {}),
  })));
  scope.runAgent3();

  if (kiRows !== null) {
    const headers = ['Week_End_Date', 'Area', 'Zone', 'District']
      .concat(...KI_KEYS.map((k) => [k + '_real', k + '_meta']))
      .concat(['leader_call', 'correlation_meeting']);
    const sheet = ss.insertSheet('WEEKLY_KI');
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    kiRows.forEach((row) => {
      sheet.appendRow(headers.map((h) => (row[h] !== undefined ? row[h] : '')));
    });
  }

  // Without a companion email the area gets no letter at all, so there would
  // be nothing to assert against.
  const orgSheet = ss.getSheetByName('MISSION_ORG');
  const orgData = orgSheet.getDataRange().getValues();
  const areaNameCol = orgData[0].indexOf('Area_Name');
  const email1Col = orgData[0].indexOf('Companion1_Email');
  for (let i = 1; i < orgData.length; i++) {
    if (orgData[i][areaNameCol] === 'Arauco 1') {
      orgSheet.getRange(i + 1, email1Col + 1).setValue('zl.arauco1@example.com');
      break;
    }
  }

  const messageBank = ss.getSheetByName('MESSAGE_BANK');
  messageBank.appendRow(['S-LR-001', 'SUNDAY_COACHING_STRENGTH', 'lesson_rate', '', '¡Excelente!', 'Cuerpo.', '174', 'Enseñar', 'Alma 26:22', 'Escritura', 'TRUE']);
  messageBank.appendRow(['G-CL-001', 'SUNDAY_COACHING_GROWTH', 'close_rate', '', 'Oportunidad', 'Cuerpo.', '205', 'Invitar', 'Moroni 10:4', 'Escritura', 'TRUE']);

  scope.runAgent1A();
  scope.runAgent1B();
  scope.runAgent1C();

  const email = env.state.emails.find((e) => e.to === 'CCSM.PMG.Compass@gmail.com');
  assert.ok(email, 'expected an email captured to the TEST_MODE inbox');
  return { body: email.htmlBody || '', weekEnd };
}

// ===========================================================================
// 1. Real KI data renders: title, all 7 labels, own-meta pairs, goal state.
// ===========================================================================
{
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const thisSunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
  const weekEnd = toDateStr(thisSunday);

  const { body } = runChain([{
    Week_End_Date: weekEnd, Area: 'Arauco 1', Zone: 'Arauco', District: 'Arauco',
    ki_new_people_real: 14, ki_new_people_meta: 8,          // goal beaten
    ki_member_lessons_real: 3, ki_member_lessons_meta: 6,   // half way
    ki_friends_sacrament_real: 0, ki_friends_sacrament_meta: 3,
    ki_friends_first_week_real: 0, ki_friends_first_week_meta: 1,
    ki_baptismal_date_real: 3, ki_baptismal_date_meta: 4,
    ki_baptized_confirmed_real: 0, ki_baptized_confirmed_meta: 0, // unset goal
    ki_rc_at_church_real: 2, ki_rc_at_church_meta: 1,
    leader_call: 'TRUE', correlation_meeting: 'TRUE',
  }]);

  assert.ok(body.includes('Indicadores Clave'), 'expected the Key Indicators block title');

  [
    'Nuevas Personas Encontradas', 'Lecciones con Miembros',
    'Amigos en la Reunión Sacramental', 'Amigos en la Iglesia (Primera Semana)',
    'Amigos con Fecha Bautismal', 'Bautizados y Confirmados',
    'Conversos Recientes en la Iglesia',
  ].forEach((label) => {
    assert.ok(body.includes(label), 'expected KI label "' + label + '" in the letter');
  });

  // The companionship's OWN meta (8), not the mission-wide nightly goal.
  assert.ok(body.includes('14 / 8'), 'expected real/meta pair rendered from WEEKLY_KI');
  assert.ok(body.includes('3 / 6'),  'expected a below-goal KI pair');

  // A meta of 0 is "nothing expected", not a 0% miss.
  assert.ok(body.includes('sin meta esta semana'), 'a zero meta must read as "sin meta", never as 0% of goal');
  assert.ok(!body.includes('0 / 0'), 'an unset goal must not render as a 0/0 pair');

  assert.ok(body.includes('Meta alcanzada'), 'expected a reached-goal caption for the beaten KI');
  assert.ok(body.includes('50% de la meta'), 'expected a percent caption for the half-way KI');

  // The KI block leads the letter: it must precede the coaching cards.
  assert.ok(body.indexOf('Indicadores Clave') < body.indexOf('Fortaleza'),
    'the KI block must appear above the coaching messages');

  assert.ok(!/Key Indicators|of goal(?!\p{L})/u.test(body),
    'no English KI strings may leak into the Spanish letter');

  console.log('KI block with real data OK');
}

// ===========================================================================
// 1b. Goal-progress colour bands (a1c_goalBandColor_): green >=90,
//     blue 50-89, yellow 1-49, red only at a genuine zero. Exercised at every
//     boundary, because an off-by-one here silently repaints a quarter of
//     every letter and nothing else would catch it.
// ===========================================================================
{
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const thisSunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());

  const GREEN = '#16a34a', BLUE = '#2563eb', YELLOW = '#a16207', RED = '#dc2626';

  // meta 100 keeps real == pct, so each KI lands on a chosen percentage.
  const { body } = runChain([{
    Week_End_Date: toDateStr(thisSunday), Area: 'Arauco 1', Zone: 'Arauco', District: 'Arauco',
    ki_new_people_real: 90, ki_new_people_meta: 100,          // 90% -> green (lower edge)
    ki_member_lessons_real: 89, ki_member_lessons_meta: 100,  // 89% -> blue (upper edge)
    ki_friends_sacrament_real: 50, ki_friends_sacrament_meta: 100,   // 50% -> blue (lower edge)
    ki_friends_first_week_real: 49, ki_friends_first_week_meta: 100, // 49% -> yellow (upper edge)
    ki_baptismal_date_real: 1, ki_baptismal_date_meta: 100,   // 1%  -> yellow (lower edge)
    ki_baptized_confirmed_real: 0, ki_baptized_confirmed_meta: 100,  // 0%  -> red
    ki_rc_at_church_real: 150, ki_rc_at_church_meta: 100,     // 150% -> green
    leader_call: 'TRUE', correlation_meeting: 'TRUE',
  }]);

  function colorOf(pctLabel) {
    const m = body.match(new RegExp('color:(#[0-9a-fA-F]{6});">' + pctLabel + '</strong>'));
    return m ? m[1].toLowerCase() : null;
  }

  assert.strictEqual(colorOf('90% de la meta'), GREEN,  '90% must be the lower edge of green');
  assert.strictEqual(colorOf('89% de la meta'), BLUE,   '89% must be the upper edge of blue');
  assert.strictEqual(colorOf('50% de la meta'), BLUE,   '50% must be the lower edge of blue');
  assert.strictEqual(colorOf('49% de la meta'), YELLOW, '49% must be the upper edge of yellow');
  assert.strictEqual(colorOf('1% de la meta'),  YELLOW, '1% must still be yellow, not red');
  assert.strictEqual(colorOf('0% de la meta'),  RED,    'a genuine zero must be red');

  // A met goal keeps its own caption, and stays green.
  assert.ok(/color:#16a34a;">Meta alcanzada/.test(body), 'a reached goal stays green');

  console.log('goal colour bands OK');
}

// ===========================================================================
// 1c. Red is reserved for a REAL zero, not merely a percentage that rounds to
//     one. 1 against a goal of 500 is 0.2% -> displays "0%" -> must still be
//     yellow: the companionship did something, and red would say they did not.
// ===========================================================================
{
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const thisSunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());

  const { body } = runChain([{
    Week_End_Date: toDateStr(thisSunday), Area: 'Arauco 1', Zone: 'Arauco', District: 'Arauco',
    ki_new_people_real: 1, ki_new_people_meta: 500,           // 0.2% -> shows 0%, but is not nothing
    ki_member_lessons_real: 0, ki_member_lessons_meta: 500,   // a true zero
    ki_friends_sacrament_real: 0, ki_friends_sacrament_meta: 0,
    ki_friends_first_week_real: 0, ki_friends_first_week_meta: 0,
    ki_baptismal_date_real: 0, ki_baptismal_date_meta: 0,
    ki_baptized_confirmed_real: 0, ki_baptized_confirmed_meta: 0,
    ki_rc_at_church_real: 0, ki_rc_at_church_meta: 0,
    leader_call: 'TRUE', correlation_meeting: 'TRUE',
  }]);

  const zeroLabels = body.match(/color:(#[0-9a-fA-F]{6});">0% de la meta<\/strong>/g) || [];
  const colors = zeroLabels.map((s) => s.match(/#[0-9a-fA-F]{6}/)[0].toLowerCase());
  assert.ok(colors.includes('#a16207'),
    'a rounded-down 0% with a nonzero actual must stay yellow, never red');
  assert.ok(colors.includes('#dc2626'),
    'a genuine zero must still be red');

  // Unset metas must take no band colour at all -- nothing was expected.
  assert.ok(body.includes('sin meta esta semana'), 'unset meta still reads as "sin meta"');
  assert.ok(!/color:#dc2626;">sin meta/.test(body), 'an unset meta must never be red');

  // The band legend must be present so the colours are self-explaining.
  assert.ok(/verde 90% o más, azul 50–89%, amarillo 1–49%, rojo cuando aún no se registra nada/.test(body),
    'the glossary must explain all four colour bands');

  console.log('red reserved for genuine zero OK');
}

// ===========================================================================
// 2. Tab exists but this area filed no weekly form -> say so plainly.
//    Seven zeros would misreport a missing report as total failure.
// ===========================================================================
{
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const thisSunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());

  const { body } = runChain([{
    Week_End_Date: toDateStr(thisSunday), Area: 'Otra Area', Zone: 'Arauco', District: 'Arauco',
    ki_new_people_real: 5, ki_new_people_meta: 5,
  }]);

  assert.ok(body.includes('Indicadores Clave'), 'the section still appears so the gap is visible');
  assert.ok(body.includes('No recibimos su informe semanal'),
    'a missing weekly report must be stated, not silently blank');
  assert.ok(!body.includes('0 / 0'), 'a missing report must never render as seven zero pairs');

  console.log('KI block with no weekly report OK');
}

// ===========================================================================
// 3. WEEKLY_KI absent entirely -> stay silent. The companionship did nothing
//    wrong, so the letter must not accuse them of a missing report.
// ===========================================================================
{
  const { body } = runChain(null);

  assert.ok(!body.includes('No recibimos su informe semanal'),
    'an unavailable source must not be reported as the companionship failing to submit');
  assert.ok(!body.includes('🎯'), 'the KI block should not render at all when the tab is unavailable');
  assert.ok(body.includes('Su Semana — Todos los Indicadores'),
    'the rest of the letter must still build normally without WEEKLY_KI');

  console.log('KI block with unavailable source OK');
}

console.log('agent1c key indicators OK');
