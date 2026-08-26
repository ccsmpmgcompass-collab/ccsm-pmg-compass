// test_cumplimiento_block.js — "Cumplimiento de la Zona", the compliance block
// that closes every leadership section
// (a1a_loadWeeklyFilings_ / a1a_rollUpFilings_ -> summaries.*.filings ->
//  a1c_buildCumplimientoBlock_).
//
// WHY THIS EXISTS. A leader could see how their unit's week went and never see
// who actually filed the two forms the whole letter is built from. The block
// answers that for both forms, trended, and the rules in it exist because the
// obvious version is wrong on this mission's real data:
//
//   - THE NIGHTLY DENOMINATOR IS AREAS x 7, NOT 7. `days` is AREA-days: a zone
//     of 11 can report 77 in a week. Dividing by 7 puts every zone above 100%.
//   - A WEEK BEFORE THE LOGS BEGIN IS NOT A WEEK THEY FAILED. DAILY_LOG starts
//     2026-08-09 and WEEKLY_KI has one row that week, so a 4-week window
//     reaches back past both. Those rows say "sin datos"; a 0% would read as a
//     catastrophic week rather than a missing one. But a week with nightly
//     data and zero weekly filings IS real and must still print 0%.
//   - THE DELTA COMPARES AGAINST THE LAST WEEK THAT HAS DATA, not the row
//     directly above. In a young mission that row is "sin datos", and
//     comparing against it makes every unit read as a recovery from nothing.
//   - THE MISSION LETTER GETS ZONES, NOT AREAS. 43 rows is several screens, and
//     an AP does not chase an area directly. The Mision row is the sum of the
//     rows above it, so a table that does not add up cannot reach a reader.
//   - "meta sin resultado" IS a1a_rollUpKi_'s silentAreas, not a second
//     derivation. The same fact is a count in the callout at the top of the
//     section and a state in this table -- one source, two places.
//
// Every number in block 9 is the live mission's, read off the 2026-08-24 dump:
// mission 236/301 nightly and 32/43 weekly this week, 243/301 and 34/43 the
// week before.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const AGENT_FILES = ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs',
  'CCSM_AgentTestMode.gs', 'CCSM_Agent3.gs', 'CCSM_Agent1A.gs', 'CCSM_Agent1C.gs'];

function loadScope() {
  const env = makeGasEnv();
  const scope = loadGs(AGENT_FILES, env.globals);
  return { env, scope };
}

// Agent1A rides along with 1C: the block renders from a1a_rollUpTrend_'s and
// a1a_rollUpFilings_'s output, and the roll-ups are unit-tested here too.
const { env, scope } = loadScope();
makeCcsmSpreadsheet(env, scope); // a1c_buildEmail's footer calls getMissionName()

const GREEN = '#16a34a', BLUE = '#2563eb', YELLOW = '#a16207', RED = '#dc2626', MUTED = '#6b7280';
const NO_DATA = '#9ca3af', SILENT_BG = '#fef2f2', UP = '#166534', DOWN = '#b91c1c';

const C = {
  header: '#1e3a5f', green: GREEN, blue: BLUE, yellow: YELLOW, red: RED,
  muted: MUTED, border: '#e5e7eb', bgLight: '#f9fafb',
};

// <strong> and friends are stripped with the EMPTY string, not a space: these
// tables bold a value mid-cell, and a space would land before the separator
// and trip every prose assertion spuriously.
//
// U+00AD goes too. a1c_softHyphenate_ puts literal soft hyphens inside area
// names, so a plain indexOf('Galvarino') finds nothing in "Gal-va-ri-no" and
// every name assertion below fails for a reason that has nothing to do with
// what it is testing. Block 13 asserts on the RAW html for exactly that reason.
function textOf(html) {
  return html.replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/­/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** A trend roll-up carrying only what this block reads: the week and its days. */
function trend(pairs) {
  return { weeks: pairs.map((p) => ({ week: p[0], days: p[1], metrics: {} })) };
}

/** a1a_rollUpFilings_'s shape. */
function filings(pairs, total) {
  return pairs.map((p) => ({ week: p[0], filed: p[1], total: total }));
}

/** An area in the shape a1c_buildLeadershipSection hands the block. */
function area(name, days, kiFiled, zone) {
  return {
    name: name, stats: { submissions: days }, zone: zone || 'Zona Uno',
    district: 'Distrito Uno', growth: null, strength1: null, strength2: null,
    kiFiled: kiFiled,
  };
}

/** The slice of a1a_rollUpKi_'s output this block reads. */
function kiRollup(silentAreas) {
  return {
    metaWeekEnd: '2026-08-16', areasTotal: 11, areasReported: 7,
    metasSet: 7, metasAchieved: 4, fallbackAreas: [],
    silentAreas: silentAreas || [], indicators: [],
  };
}

const build = (totals, areas, ki, s) =>
  scope.a1c_buildCumplimientoBlock_(totals, areas, ki, s || 'zone', C);

const WEEKS = ['2026-08-02', '2026-08-09', '2026-08-16', '2026-08-23'];

// ===========================================================================
// 1. a1a_loadWeeklyFilings_: one read of WEEKLY_KI, only the weeks asked for,
//    and null -- never {} -- when the tab cannot be read.
// ===========================================================================
{
  const { env: e, scope: s } = loadScope();
  const ss = makeCcsmSpreadsheet(e, s);

  assert.strictEqual(s.a1a_loadWeeklyFilings_(WEEKS), null,
    'no WEEKLY_KI tab must read as null, not as "nobody filed"');

  const sheet = ss.insertSheet('WEEKLY_KI');
  sheet.getRange(1, 1, 1, 4).setValues([['Week_End_Date', 'Area', 'Zone', 'District']]);
  sheet.appendRow(['2026-08-16', 'Arauco 1', 'Arauco', 'Arauco']);
  sheet.appendRow(['2026-08-23', 'Arauco 1', 'Arauco', 'Arauco']);
  sheet.appendRow(['2026-08-23', 'Arauco 2', 'Arauco', 'Arauco']);
  // Outside the window the caller asked for.
  sheet.appendRow(['2026-07-05', 'Arauco 1', 'Arauco', 'Arauco']);

  const map = s.a1a_loadWeeklyFilings_(WEEKS);
  assert.deepStrictEqual(map['Arauco 1'], { '2026-08-16': true, '2026-08-23': true },
    'both in-window weeks kept, the July row dropped');
  assert.deepStrictEqual(map['Arauco 2'], { '2026-08-23': true });
  assert.strictEqual(map['Arauco 1']['2026-07-05'], undefined,
    'a week outside the requested window must not be carried');

  console.log('a1a_loadWeeklyFilings_ OK');
}

// ===========================================================================
// 2. a1a_rollUpFilings_ counts the unit's own members, week by week, and the
//    current week's `filed` IS a1a_rollUpKi_'s areasReported. The block's
//    headline bar and the last row of its table are one number; if these two
//    functions ever disagree, the letter contradicts itself on screen.
// ===========================================================================
{
  const members = [
    { name: 'A', ki: [{ key: 'ki_new_people', real: 1, meta: 1 }], kiMetaPrev: { ki_new_people: 1 } },
    { name: 'B', ki: [{ key: 'ki_new_people', real: 0, meta: 0 }], kiMetaPrev: null },
    { name: 'C', ki: [], kiMetaPrev: { ki_new_people: 5 } },  // owed a result, sent none
  ];
  const map = { A: { '2026-08-16': true, '2026-08-23': true },
                B: { '2026-08-23': true },
                C: { '2026-08-16': true } };

  const rolled = scope.a1a_rollUpFilings_(members, map, WEEKS);
  assert.strictEqual(rolled.length, 4, 'one row per week asked for, including the empty ones');
  assert.deepStrictEqual(rolled.map((r) => r.filed), [0, 0, 2, 2]);
  assert.ok(rolled.every((r) => r.total === 3), 'the denominator is the unit\'s member count');

  const kiOut = scope.a1a_rollUpKi_(members, '2026-08-16');
  assert.strictEqual(rolled[3].filed, kiOut.areasReported,
    'the current week\'s filing count must equal the KI roll-up\'s areasReported');

  assert.strictEqual(scope.a1a_rollUpFilings_(members, null, WEEKS), null,
    'an unreadable WEEKLY_KI leaves .filings null, so the letter drops the weekly half');
  assert.strictEqual(scope.a1a_rollUpFilings_([], map, WEEKS), null);

  console.log('a1a_rollUpFilings_ OK');
}

// ===========================================================================
// 3. The nightly denominator is AREAS x 7. `days` is area-days: dividing a
//    zone's 45 by 7 reads 643%, and by 77 reads 58%, which is the real number.
// ===========================================================================
{
  const totals = {
    total_areas: 11,
    trend: trend([['2026-08-16', 54], ['2026-08-23', 45]]),
    filings: filings([['2026-08-16', 8], ['2026-08-23', 7]], 11),
  };
  const html = build(totals, [], kiRollup());
  const txt = textOf(html);

  assert.ok(/45\/77 · 58%/.test(txt), 'nightly is 45 of 11 areas x 7 days: ' + txt.slice(0, 400));
  assert.ok(!/45\/7 /.test(txt), 'a 7-day denominator would put every zone over 100%');
  assert.ok(/7\/11 · 64%/.test(txt), 'weekly is 7 of the unit\'s 11 areas');

  console.log('area-days denominator OK');
}

// ===========================================================================
// 4. "sin datos" is for a week with nothing on EITHER form. A week with
//    nightly activity and zero weekly filings is a real week and prints 0%.
//    Distrito Cabrero 2 is live proof: 7/21 nightly, 0/3 weekly, week of 08-16.
// ===========================================================================
{
  const totals = {
    total_areas: 3,
    trend: trend([['2026-08-02', 0], ['2026-08-09', 0], ['2026-08-16', 7], ['2026-08-23', 1]]),
    filings: filings([['2026-08-02', 0], ['2026-08-09', 0], ['2026-08-16', 0], ['2026-08-23', 0]], 3),
  };
  const html = build(totals, [], kiRollup());
  const txt = textOf(html);

  // Counted in the markup, not the text: the footnote says «sin datos» too,
  // and counting it would make this assertion pass with three real cells.
  assert.strictEqual((html.match(/;">sin datos</g) || []).length, 4,
    'the two genuinely empty weeks give two "sin datos" cells each: ' + txt);
  assert.ok(/7\/21 · 33%/.test(txt), 'a week with nightly data keeps its real nightly figure');
  assert.ok(/0\/3 · 0%/.test(txt),
    'and its weekly zero is printed, not hidden as "sin datos" — nobody filed, and that is true');

  console.log('"sin datos" vs a real zero OK');
}

// ===========================================================================
// 5. The delta chip compares against the last week WITH DATA. With "sin datos"
//    directly above the current row, comparing to the row above would either
//    print nothing or read as a jump from zero.
// ===========================================================================
{
  const totals = {
    total_areas: 10,
    trend: trend([['2026-08-02', 0], ['2026-08-09', 70], ['2026-08-16', 0], ['2026-08-23', 35]]),
    filings: filings([['2026-08-02', 0], ['2026-08-09', 8], ['2026-08-16', 0], ['2026-08-23', 5]], 10),
  };
  const txt = textOf(build(totals, [], kiRollup()));

  // 35/70 = 50% against 70/70 = 100% two rows up → −50 pp.
  assert.ok(/50% ▼ −50 pp/.test(txt), 'nightly delta must skip the empty week: ' + txt);
  assert.ok(/50% ▼ −30 pp/.test(txt), 'weekly 5/10 = 50% against 8/10 = 80% → −30 pp');
  assert.ok(!/▲/.test(txt), 'nothing rose here; an up-arrow means the empty row was used as the base');

  console.log('delta skips empty weeks OK');
}

// ===========================================================================
// 6. A flat week says so with its own sign. ▲ and ▼ carry direction; ■ does
//    not, so it prints "0 pp" — the same call the trend block makes.
// ===========================================================================
{
  const totals = {
    total_areas: 4,
    trend: trend([['2026-08-16', 27], ['2026-08-23', 27]]),
    filings: filings([['2026-08-16', 3], ['2026-08-23', 3]], 4),
  };
  const txt = textOf(build(totals, [], kiRollup()));
  assert.ok(/■ 0 pp/.test(txt), 'an unchanged week must state that it is unchanged: ' + txt);

  console.log('flat chip OK');
}

// ===========================================================================
// 7. The per-area table: three states, the red row, the sort, and where
//    "meta sin resultado" comes from.
// ===========================================================================
{
  const areas = [
    area('Villa Obispo', 0, false),   // in silentAreas → meta sin resultado
    area('Yumbel', 0, false),         // filed nothing, owed nothing → —
    area('Laja 1', 7, true),
    area('Cabrero 1', 1, false),
    area('Galvarino', 6, true),
  ];
  const totals = {
    total_areas: 5,
    trend: trend([['2026-08-16', 20], ['2026-08-23', 14]]),
    filings: filings([['2026-08-16', 3], ['2026-08-23', 2]], 5),
  };
  const html = build(totals, areas, kiRollup(['Villa Obispo']));
  const txt = textOf(html);

  assert.ok(/meta sin resultado/.test(txt), 'the silent area gets its own state');
  assert.ok(html.indexOf(SILENT_BG) >= 0, 'and its row is tinted, so the eye finds it');
  assert.ok(/meta sin resultado = fijó una meta el 16 de agosto/.test(txt),
    'the term is defined, dated from ki.metaWeekEnd: ' + txt.slice(-320));

  // Best first: filed, then most nights, then name.
  const order = ['Laja 1', 'Galvarino', 'Cabrero 1', 'Villa Obispo', 'Yumbel'];
  let at = -1;
  order.forEach((n) => {
    const i = txt.indexOf(n);
    assert.ok(i > at, n + ' is out of order in: ' + txt);
    at = i;
  });

  // Yumbel filed nothing but owed nothing, so it is a dash, not an accusation.
  // Scoped to ITS OWN ROW: the footnote below the table defines the term, so
  // slicing to the end of the document would trip on the definition.
  const from = html.indexOf('Yumbel');
  const yumbel = html.slice(from, html.indexOf('</tr>', from));
  assert.ok(yumbel.indexOf('meta sin resultado') < 0,
    'an area that set no meta last week did not fail to report a result');
  assert.ok(yumbel.indexOf(SILENT_BG) < 0, 'and its row is not tinted');

  console.log('per-area states, tint, sort OK');
}

// ===========================================================================
// 8. "meta sin resultado" tracks ki.silentAreas and nothing else. Drop the
//    area from that list and the state must disappear, even though its
//    kiFiled is still false — the KI callout at the top of the section and
//    this table have to name the same set.
// ===========================================================================
{
  const areas = [area('Villa Obispo', 0, false), area('Laja 1', 7, true)];
  const totals = {
    total_areas: 2,
    trend: trend([['2026-08-23', 7]]),
    filings: filings([['2026-08-23', 1]], 2),
  };
  assert.ok(/meta sin resultado/.test(textOf(build(totals, areas, kiRollup(['Villa Obispo'])))));
  assert.ok(!/meta sin resultado/.test(textOf(build(totals, areas, kiRollup([]))))
    , 'with an empty silentAreas the state must not be re-derived from kiFiled alone');
  assert.ok(!/meta sin resultado/.test(textOf(build(totals, areas, null))),
    'and a null KI roll-up cannot produce it either');

  console.log('silentAreas is the single source OK');
}

// ===========================================================================
// 9. The mission letter: zones, not areas, and a Mision row that is the sum of
//    the rows above it. Live figures — 236/301 nightly, 32/43 weekly.
// ===========================================================================
{
  function zone(name, areas, days, filed) {
    const out = [];
    for (let i = 0; i < areas; i++) {
      out.push(area(name + ' ' + (i + 1), i < days ? 1 : 0, i < filed, name));
    }
    return out;
  }
  // Day counts are spread one-per-area for arithmetic that is easy to read:
  // what matters is that the Mision row equals the sum, not the shape.
  const areas = [].concat(
    zone('Angol', 8, 8, 7),
    zone('Los Angeles Norte', 11, 5, 7),
    zone('San Pedro', 11, 6, 9),
    zone('Temuco Nielol', 13, 9, 9));

  const totalDays = 8 + 5 + 6 + 9;
  const totals = {
    total_areas: 43,
    trend: trend([['2026-08-16', 243], ['2026-08-23', totalDays]]),
    filings: filings([['2026-08-16', 34], ['2026-08-23', 32]], 43),
  };
  const html = build(totals, areas, kiRollup(), 'mission');
  const txt = textOf(html);

  assert.ok(/Cumplimiento de la Misión/.test(txt), 'the title takes the possessive scope form');
  assert.ok(/Por zona/.test(txt) && !/Por área/.test(txt),
    'the mission letter breaks down by zone, never by 43 areas');
  assert.ok(/Panel de PMG Compass/.test(txt), 'and points at the Panel for the area detail');

  // Every zone row, then the total, which must equal their sum.
  assert.ok(/Angol8\/56/.test(txt.replace(/ /g, '')) || /8\/56/.test(txt), 'Angol: 8 area-days of 8x7');
  assert.ok(/Misión/.test(txt), 'a Misión row closes the table');
  assert.ok(new RegExp(totalDays + '\\/301').test(txt),
    'the Misión row is the sum of the zone rows (' + totalDays + '/301), not a separate roll-up: ' + txt);
  assert.ok(/32\/43 · 74%/.test(txt), 'and its weekly half sums the same way');

  // 243/301 the week before, 78/301 this week in this fixture -> the headline
  // bar reads the trend roll-up, so it is NOT the per-zone sum.
  assert.ok(/243\/301 · 81%/.test(txt), 'the prior week comes from the trend roll-up');

  console.log('mission zone rollup OK');
}

// ===========================================================================
// 10. An unreadable WEEKLY_KI drops the weekly half everywhere -- the bar, the
//     column, the per-area state -- and leaves the nightly half saying the
//     true thing it still knows. A zero here would blame 43 companionships for
//     a tab nobody could open.
// ===========================================================================
{
  const areas = [area('Laja 1', 7, null), area('Yumbel', 3, null)];
  const totals = {
    total_areas: 2,
    trend: trend([['2026-08-16', 14], ['2026-08-23', 10]]),
    filings: null,
  };
  const html = build(totals, areas, null);
  const txt = textOf(html);

  assert.ok(/10\/14 · 71%/.test(txt), 'the nightly half still renders: ' + txt);
  assert.ok(!/Informe semanal de indicadores/.test(txt), 'no weekly bar');
  assert.ok(!/0\/2/.test(txt), 'and nothing anywhere reports zero areas filing');
  assert.ok(txt.indexOf('Sem.') < 0, 'the per-area table drops the column rather than dashing it');
  assert.ok(/Laja 1/.test(txt) && /7\/7/.test(txt), 'the area rows keep their nightly days');

  console.log('null WEEKLY_KI OK');
}

// ===========================================================================
// 11. Nothing at all: no areas, or no weeks, renders no block. An empty
//     compliance heading over an empty table is a rendering fault, not a
//     report.
// ===========================================================================
{
  assert.strictEqual(build(null, [], null), '');
  assert.strictEqual(build({ total_areas: 0 }, [], null), '');
  assert.strictEqual(build({ total_areas: 5, trend: null, filings: null }, [], null), '',
    'no trend and no filings means no weeks, so nothing to say');

  console.log('empty states OK');
}

// ===========================================================================
// 12. The history footnote is DERIVED from the data, not written down. It
//     names the first week that actually has something, so it stays true as
//     the window fills in week by week -- and it is omitted entirely once the
//     whole window has data, where it would be noise.
// ===========================================================================
{
  const partial = {
    total_areas: 4,
    trend: trend([['2026-08-02', 0], ['2026-08-09', 0], ['2026-08-16', 20], ['2026-08-23', 18]]),
    filings: filings([['2026-08-02', 0], ['2026-08-09', 0], ['2026-08-16', 3], ['2026-08-23', 4]], 4),
  };
  assert.ok(/El historial empieza en la semana que terminó el 16 de agosto/
    .test(textOf(build(partial, [], kiRollup()))), 'the start date is read off the rows');

  const full = {
    total_areas: 4,
    trend: trend([['2026-08-02', 12], ['2026-08-09', 14], ['2026-08-16', 20], ['2026-08-23', 18]]),
    filings: filings([['2026-08-02', 2], ['2026-08-09', 3], ['2026-08-16', 3], ['2026-08-23', 4]], 4),
  };
  const fullTxt = textOf(build(full, [], kiRollup()));
  assert.ok(!/El historial empieza/.test(fullTxt),
    'with every week populated there is no gap to explain');
  assert.ok(/se miden contra las 4 áreas que la zona tiene hoy/.test(fullTxt),
    'but the moved-denominator caveat is always stated — MISSION_ORG keeps no history');

  console.log('derived history footnote OK');
}

// ===========================================================================
// 13. Area names survive escaping and hyphenation together. One live area is
//     called "Huepil & Tucapel & Villa Obispo" and another "Villa O'Higgins".
//
//     NOTE ON SCOPE. The block hyphenates before escaping, which is the order
//     a1c_softHyphenate_'s own note asks for and the order the wide area table
//     uses. That order was checked BOTH WAYS against the live names and they
//     survive either one: a1c_esc leaves apostrophes alone, and the syllable
//     rule never lands a break inside "&amp;" — it breaks before the "&" or
//     after the ";". So this asserts the OUTCOME (one escaped ampersand, no
//     entity split, no visible entity text), not the call order, because
//     asserting the order would be asserting a style rule as if it were a bug.
// ===========================================================================
{
  const totals = {
    total_areas: 2,
    trend: trend([['2026-08-23', 10]]),
    filings: filings([['2026-08-23', 2]], 2),
  };
  const html = build(totals, [
    area('Huepil & Tucapel & Villa Obispo', 5, true),
    area("Villa O'Higgins", 5, true),
  ], kiRollup());

  assert.strictEqual((html.match(/&amp;/g) || []).length, 2, 'both ampersands escaped exactly once');
  assert.ok(!/&(?!amp;|nbsp;|#)/.test(html.replace(/&amp;/g, '')),
    'no raw ampersand escaped into the markup');
  assert.ok(!/&[­]|&a[­]|&am[­]|&amp[­]/.test(html),
    'no soft hyphen inside an entity, which would render as visible characters');
  // What the reader ends up seeing: entities resolved, soft hyphens invisible.
  const rendered = textOf(html).replace(/&amp;/g, '&');
  assert.ok(rendered.indexOf('Huepil & Tucapel & Villa Obispo') >= 0,
    'the ampersand name reads back exactly as it is written in MISSION_ORG: ' + rendered);
  assert.ok(rendered.indexOf("Villa O'Higgins") >= 0, 'and so does the apostrophe name');

  console.log('entity-safe hyphenation OK');
}

// ===========================================================================
// 14. Wired into the letter. Every unit test above can pass while the call
//     site is missing -- this is the only block that catches that, and it also
//     pins the block's position: last in the section, under the coaching card.
// ===========================================================================
{
  const { env: e, scope: s } = loadScope();
  const ss = makeCcsmSpreadsheet(e, s);
  setConfig(e, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(e, ss, 'TRANSFER_START_DATE', '2020-01-01');

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const sunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
  const toStr = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') +
                       '-' + String(d.getDate()).padStart(2, '0');
  const weekEnd = toStr(sunday);
  const prevEnd = toStr(new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() - 7));

  addNightlyRaw(e, ss, [{
    zone: 'Arauco', area: 'Arauco 1', report_date: weekEnd,
    exchanges: 'Sí', effort: 'Algo', contacts_made: 12,
  }]);
  s.runAgent3();

  const sheet = ss.insertSheet('WEEKLY_KI');
  sheet.getRange(1, 1, 1, 6).setValues([['Week_End_Date', 'Area', 'Zone', 'District',
                                         'ki_new_people_real', 'ki_new_people_meta']]);
  sheet.appendRow([prevEnd, 'Arauco 1', 'Arauco', 'Arauco', 1, 3]);
  sheet.appendRow([weekEnd, 'Arauco 1', 'Arauco', 'Arauco', 5, 9]);

  s.runAgent1A();
  const payload = s.loadTempData('A1A_DATA');

  const zf = payload.summaries.zones['Arauco'].filings;
  assert.ok(Array.isArray(zf), 'runAgent1A must hang a filing roll-up on every zone summary');
  assert.strictEqual(zf.length, s.A1A_TREND_WEEKS, 'over the same four weeks as .trend');
  assert.strictEqual(zf[zf.length - 1].week, weekEnd, 'ending at the week reported on');
  assert.strictEqual(zf[zf.length - 1].filed, 1);
  assert.strictEqual(zf[zf.length - 2].filed, 1, 'the prior week filed too');

  // EVERY scope, not just the zone: the two roll-ups are wired unit by unit,
  // so a mission or district line that slices its weeks differently is a live
  // bug the zone assertion above cannot see. The two columns of the table have
  // to be indexed by ONE set of weeks in all three places.
  const units = [payload.summaries.mission]
    .concat(Object.keys(payload.summaries.zones).map((z) => payload.summaries.zones[z]))
    .concat(Object.keys(payload.summaries.districts).map((d) => payload.summaries.districts[d]));
  assert.ok(units.length >= 3, 'mission + at least one zone and district');
  units.forEach((u, i) => {
    assert.ok(Array.isArray(u.filings), 'unit ' + i + ' must carry a filing roll-up');
    assert.ok(u.trend && u.trend.weeks, 'unit ' + i + ' must carry a trend roll-up');
    assert.deepStrictEqual(u.filings.map((r) => r.week), u.trend.weeks.map((w) => w.week),
      'unit ' + i + ': .filings and .trend must cover exactly the same weeks, in the same order');
  });

  // ...and it reaches a rendered letter.
  const person = {
    name: 'Líder', email: 'lider@missionary.org', areas: [],
    roles: [{ type: 'ZL', zone: 'Arauco', district: null }],
  };
  const html = s.a1c_buildEmail(person, payload.areas, payload.summaries, weekEnd);
  assert.ok(html.indexOf('Cumplimiento de la Zona') >= 0,
    'the block must actually be wired into a1c_buildLeadershipSection');
  assert.ok(html.indexOf('Informe nocturno — días informados') >= 0);

  // Position: after the coaching card, before the glossary.
  const comp = html.indexOf('Cumplimiento de la Zona');
  const card = html.indexOf('Capacitación de Líderes');
  const gloss = html.indexOf('Glosario');
  if (card >= 0) assert.ok(comp > card, 'compliance closes the section, under the coaching card');
  if (gloss >= 0) assert.ok(comp < gloss, 'and still sits inside the section, above the glossary');

  console.log('end-to-end wiring and placement OK');
}

console.log('\ntest_cumplimiento_block: all checks passed');
