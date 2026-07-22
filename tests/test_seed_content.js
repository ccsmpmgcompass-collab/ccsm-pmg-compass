// test_seed_content.js — CCSM_SeedContent.gs
//
// Verifies the Spanish MESSAGE_BANK + KNOWLEDGE_BASE seed content:
//   * row counts per category match the content matrix
//   * every Metric value is a real CCSM metric key (derived from
//     CcsmData.gs / CCSM_Agent1A.gs, never hardcoded here)
//   * Message_IDs are unique and every row is Active
//   * no English leaks into Spanish body/subject text
//   * Scripture_Text is blank on every row, including the two rows whose
//     subject/body came verbatim from the task brief (HARD RULE: never
//     fabricate scripture text — a blank cell is the correct answer when
//     the exact Spanish LDS wording isn't verified)
//   * getMessageBank() can read the seeded rows back by header lookup
//   * re-running the seeders is idempotent (they clear rows 2+ first)
const assert = require('assert');
const fs = require('fs');
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet } = require('./fixtures');

const env = makeGasEnv();
const scope = loadGs(
  [
    'CcsmData.gs',
    'BuildCcsmSheet.gs',
    'CCSM_Helpers.gs',
    'CCSM_AgentTestMode.gs',
    'CCSM_Agent1A.gs',
    'CCSM_SeedContent.gs'
  ],
  env.globals
);
const ss = makeCcsmSpreadsheet(env, scope);

// ---------------------------------------------------------------------------
// Expected metric keys — DERIVED from the real data module, not restated.
// Count metrics = the NUMBER-typed nightly questions (20).
// Rate metrics  = A1A_RATE_METRICS (5).
// ---------------------------------------------------------------------------
const COUNT_METRICS = scope.CCSM_NIGHTLY_QUESTIONS.filter((q) => q.type === 'NUMBER').map((q) => q.key);
const RATE_METRICS = scope.A1A_RATE_METRICS.map((m) => m.key);
const ALL_METRICS = RATE_METRICS.concat(COUNT_METRICS);

assert.strictEqual(COUNT_METRICS.length, 20, 'brief assumes 20 count metrics');
assert.strictEqual(RATE_METRICS.length, 5, 'brief assumes 5 rate metrics');

const EXPECTED_TOTAL = ALL_METRICS.length * 3 * 2 + COUNT_METRICS.length * 2 + 3; // 75 + 75 + 40 + 3

// ---------------------------------------------------------------------------
// Run the seeders
// ---------------------------------------------------------------------------
scope.seedCcsmMessageBank();
scope.seedCcsmKnowledgeBase();

function readTab(name) {
  const data = ss.getSheetByName(name).getDataRange().getValues();
  const headers = data[0].map((h) => String(h).trim());
  const rows = data.slice(1).map((r) => {
    const o = {};
    headers.forEach((h, i) => (o[h] = r[i] === undefined ? '' : String(r[i])));
    return o;
  });
  return { headers, rows };
}

// ---------------------------------------------------------------------------
// MESSAGE_BANK — header row must match CCSM_TAB_SPECS (getMessageBank() does a
// header-name lookup, so a drifted header silently breaks every agent).
// ---------------------------------------------------------------------------
const mbSpec = scope.CCSM_TAB_SPECS.find((t) => t.name === 'MESSAGE_BANK');
const mb = readTab('MESSAGE_BANK');
assert.deepStrictEqual(mb.headers, mbSpec.headers, 'MESSAGE_BANK header must match CCSM_TAB_SPECS');

// Row counts per category
const byCat = {};
mb.rows.forEach((r) => {
  byCat[r.Category] = (byCat[r.Category] || 0) + 1;
});
assert.strictEqual(mb.rows.length, EXPECTED_TOTAL, 'total MESSAGE_BANK rows');
assert.strictEqual(byCat['SUNDAY_COACHING_STRENGTH'], 75);
assert.strictEqual(byCat['SUNDAY_COACHING_GROWTH'], 75);
assert.strictEqual(byCat['FRIDAY_ENCOURAGEMENT'], 40);
assert.strictEqual(byCat['MISSED_DAYS'], 3);
assert.deepStrictEqual(
  Object.keys(byCat).sort(),
  ['FRIDAY_ENCOURAGEMENT', 'MISSED_DAYS', 'SUNDAY_COACHING_GROWTH', 'SUNDAY_COACHING_STRENGTH'],
  'no stray categories (agents only consume these four)'
);

// Per-metric coverage: 3 strength + 3 growth for every metric, 2 Friday for
// every count metric. A missing metric means pickMessage() returns null and
// that area silently gets no coaching message.
ALL_METRICS.forEach((key) => {
  const s = mb.rows.filter((r) => r.Category === 'SUNDAY_COACHING_STRENGTH' && r.Metric === key);
  const g = mb.rows.filter((r) => r.Category === 'SUNDAY_COACHING_GROWTH' && r.Metric === key);
  assert.strictEqual(s.length, 3, 'strength rows for ' + key);
  assert.strictEqual(g.length, 3, 'growth rows for ' + key);
});
COUNT_METRICS.forEach((key) => {
  const f = mb.rows.filter((r) => r.Category === 'FRIDAY_ENCOURAGEMENT' && r.Metric === key);
  assert.strictEqual(f.length, 2, 'friday rows for ' + key);
});

// Every Metric value is a real key (or blank for MISSED_DAYS, which Agent3
// selects by Category alone).
mb.rows.forEach((r) => {
  if (r.Category === 'MISSED_DAYS') {
    assert.strictEqual(r.Metric, '', 'MISSED_DAYS rows carry no metric');
  } else {
    assert.ok(ALL_METRICS.indexOf(r.Metric) >= 0, 'unknown metric key: ' + r.Metric + ' (' + r.Message_ID + ')');
  }
});

// Active + unique IDs
const ids = new Set();
mb.rows.forEach((r) => {
  assert.strictEqual(r.Active, 'TRUE', r.Message_ID + ' must be Active=TRUE');
  assert.ok(/^MSG-[A-Z]{2}(-[A-Z0-9]+)?-\d{2}$/.test(r.Message_ID), 'Message_ID format: ' + r.Message_ID);
  assert.ok(!ids.has(r.Message_ID), 'duplicate Message_ID: ' + r.Message_ID);
  ids.add(r.Message_ID);
});

// Content shape: non-empty subject + 2–4 sentence body.
const ENGLISH_LEAK = /[a-z]+ (the|your|this) /i;
mb.rows.forEach((r) => {
  assert.ok(r.Subject_Line.length > 0, r.Message_ID + ' needs a subject');
  assert.ok(r.Body_Text.length >= 80, r.Message_ID + ' body too short');
  assert.ok(r.Body_Text.length <= 600, r.Message_ID + ' body too long');
  assert.ok(!ENGLISH_LEAK.test(r.Body_Text), 'English leak in ' + r.Message_ID + ': ' + r.Body_Text);
  assert.ok(!ENGLISH_LEAK.test(r.Subject_Line), 'English leak in subject of ' + r.Message_ID);
  const sentences = (r.Body_Text.match(/[.!?…](\s|$)/g) || []).length;
  assert.ok(sentences >= 2 && sentences <= 4, r.Message_ID + ' should be 2–4 sentences, found ' + sentences);
});

// Bodies must be genuinely distinct, not one template stamped 193 times.
const bodies = new Set(mb.rows.map((r) => r.Body_Text));
assert.strictEqual(bodies.size, mb.rows.length, 'every Body_Text must be unique');

// HARD RULE: Scripture_Text is blank on every row — the exact Spanish LDS
// wording is never verified for any row, including the two whose subject/
// body came verbatim from the task brief, so fabricating verse text is
// never acceptable anywhere in the bank.
mb.rows.forEach((r) => {
  assert.strictEqual(r.Scripture_Text, '', 'Scripture_Text must be blank: ' + r.Message_ID);
});

// Scripture references, where present, use Spanish LDS book names.
const SPANISH_BOOKS = /^(D\. y C\.|1 Nefi|2 Nefi|3 Nefi|4 Nefi|Jacob|Enós|Omni|Mosíah|Alma|Helamán|Mormón|Éter|Moroni|Moisés|Abraham|José Smith)/;
mb.rows.forEach((r) => {
  if (r.Scripture !== '') {
    assert.ok(SPANISH_BOOKS.test(r.Scripture), 'non-Spanish scripture reference in ' + r.Message_ID + ': ' + r.Scripture);
  }
  // No guessed page numbers: PMG references are chapter-level everywhere,
  // including the two brief-supplied rows (the Spanish edition paginates
  // differently from the English one, so page numbers would be guesses).
  if (r.PMG_Chapter !== '') {
    assert.ok(/^Capítulo \d+$/.test(r.PMG_Chapter), 'PMG_Chapter must be chapter-level: ' + r.Message_ID + ' = ' + r.PMG_Chapter);
  }
  // PMG_Description must never re-state the "Predicad Mi Evangelio" label —
  // a1c_formatPmgRef() (CCSM_Agent1C.gs) already prepends it at render time,
  // and a row that repeats it doubles the label in the rendered email.
  assert.ok(
    !/predicad mi evangelio/i.test(r.PMG_Description),
    'PMG_Description must not repeat the "Predicad Mi Evangelio" label: ' + r.Message_ID
  );
});

// The two brief-supplied rows: subject/body must appear character-for-
// character as given in the task brief, but their PMG/scripture fields
// must be normalized to the same convention as every other row (chapter-
// level PMG reference, no page number, blank Scripture_Text) rather than
// carrying unverified page numbers and quoted verse text.
const briefRows = {
  'MSG-CS-ROLEPLAYS-01': [
    'MSG-CS-ROLEPLAYS-01', 'SUNDAY_COACHING_STRENGTH', 'roleplays', '',
    '¡Su preparación se nota!',
    'Esta semana su área se destacó en las prácticas de enseñanza. El Señor honra la preparación diligente: ' +
    'cada práctica les acerca más a enseñar con el Espíritu. ¡Sigan así!',
    'Capítulo 10', 'La práctica mejora la enseñanza',
    'D. y C. 84:85', '', 'TRUE'
  ],
  'MSG-CG-CONTACTS-01': [
    'MSG-CG-CONTACTS-01', 'SUNDAY_COACHING_GROWTH', 'contacts_attempted', '',
    'Una invitación: abran la boca',
    'Esta semana hubo menos intentos de contacto que de costumbre. Recuerden que cada persona es un hijo de Dios ' +
    'que espera escuchar el evangelio. Fijen una meta pequeña para mañana: cinco intentos más que hoy.',
    'Capítulo 9', 'Hablar con todos',
    'D. y C. 33:8-10', '', 'TRUE'
  ]
};
Object.keys(briefRows).forEach((id) => {
  const row = mb.rows.find((r) => r.Message_ID === id);
  assert.ok(row, 'brief-supplied row missing: ' + id);
  const flat = mb.headers.map((h) => row[h]);
  assert.deepStrictEqual(flat, briefRows[id], 'brief-supplied row must match normalized values: ' + id);
});

// ---------------------------------------------------------------------------
// getMessageBank() must read the seeded rows back through its header lookup.
// ---------------------------------------------------------------------------
const picked = scope.getMessageBank('SUNDAY_COACHING_STRENGTH', 'roleplays');
assert.strictEqual(picked.length, 3, 'getMessageBank returns 3 roleplays strength rows');
picked.forEach((m) => assert.strictEqual(m.metric, 'roleplays'));
assert.ok(picked.some((m) => m.messageId === 'MSG-CS-ROLEPLAYS-01'));
assert.strictEqual(scope.getMessageBank('SUNDAY_COACHING_GROWTH', 'close_rate').length, 3);
assert.strictEqual(scope.getMessageBank('FRIDAY_ENCOURAGEMENT', 'bom_shared').length, 2);

// ---------------------------------------------------------------------------
// KNOWLEDGE_BASE — 10 starter rows
// ---------------------------------------------------------------------------
const kbSpec = scope.CCSM_TAB_SPECS.find((t) => t.name === 'KNOWLEDGE_BASE');
const kb = readTab('KNOWLEDGE_BASE');
assert.deepStrictEqual(kb.headers, kbSpec.headers, 'KNOWLEDGE_BASE header must match CCSM_TAB_SPECS');
assert.strictEqual(kb.rows.length, 10, 'KNOWLEDGE_BASE starter rows');
const kbIds = new Set();
kb.rows.forEach((r) => {
  assert.ok(!kbIds.has(r.ID), 'duplicate KB ID: ' + r.ID);
  kbIds.add(r.ID);
  assert.ok(r.Question.length > 0 && r.Answer.length > 0, r.ID + ' needs a question and answer');
  assert.ok(!ENGLISH_LEAK.test(r.Answer), 'English leak in KB ' + r.ID);
  assert.strictEqual(r.UseCount, '0');
});
// One row per weekly key indicator, drawn from WeeklyReportForm_ES.gs.
const kiRows = kb.rows.filter((r) => r.Category === 'Indicadores Clave');
assert.strictEqual(kiRows.length, 7, 'one KB row per weekly key indicator');
// Support contact — never hardcoded, always read from AGENT_CONFIG.
assert.ok(
  kb.rows.some((r) => r.Answer.indexOf(scope.getConfig('SEND_FROM_EMAIL')) >= 0),
  'a KB row must give the support email address'
);

// ---------------------------------------------------------------------------
// Idempotency — re-running must not duplicate rows (clears rows 2+ first).
// ---------------------------------------------------------------------------
scope.seedCcsmMessageBank();
scope.seedCcsmKnowledgeBase();
assert.strictEqual(readTab('MESSAGE_BANK').rows.length, EXPECTED_TOTAL, 'seeding is idempotent');
assert.strictEqual(readTab('KNOWLEDGE_BASE').rows.length, 10, 'KB seeding is idempotent');

// ---------------------------------------------------------------------------
// Source hygiene — no Provo residue, no confidential Provo data.
// ---------------------------------------------------------------------------
const src = fs.readFileSync('CCSM_SeedContent.gs', 'utf8');
assert.ok(!/Utah Provo/i.test(src), 'no Provo mission name in CCSM source');
assert.ok(!/America\/Denver/.test(src), 'no Provo timezone');
assert.ok(!/\bpmg\.compass@gmail\.com\b/i.test(src), 'no Provo support inbox');

// ---------------------------------------------------------------------------
// CONTENT_REVIEW.md generator — the distinct-reference count must be computed
// from the real data, never left as a stale/placeholder literal (regression
// for the "0 distinct references" bug: the placeholder sentence was emitted
// before the refs map existed, only fixed up afterward by a whole-document
// string replace that nothing verified).
// ---------------------------------------------------------------------------
const { execFileSync } = require('child_process');
execFileSync(process.execPath, ['tools/gen_content_review.js']);
const reviewMd = fs.readFileSync('CONTENT_REVIEW.md', 'utf8');
assert.ok(!/(?<!\d)0 distinct references/.test(reviewMd), 'CONTENT_REVIEW.md must never claim 0 distinct references');
const distinctRefs = new Set(mb.rows.filter((r) => r.Scripture !== '').map((r) => r.Scripture));
const statedMatch = reviewMd.match(/There are only (\d+) distinct references/);
assert.ok(statedMatch, 'CONTENT_REVIEW.md must state the distinct-reference count');
assert.strictEqual(
  Number(statedMatch[1]),
  distinctRefs.size,
  'stated distinct-reference count must match the actual number of distinct scripture references in the bank'
);

// ── The leadership messages must appear in CONTENT_REVIEW.md ───────────────
// Final-review finding (content I-3/I-4). CONTENT_REVIEW.md claimed to list
// every missionary-facing word, but covered only the seeded banks. The
// hardcoded _LEADERSHIP_MSGS in CCSM_Agent1C.gs — which carry hand-written
// Spanish scripture text, the exact thing the blank-Scripture_Text rule exists
// to prevent, and at least two of them attached to the wrong verse — were
// invisible to the human reviewing the content, and went to the mission
// president.
//
// Asserting every reference is present keeps the doc honest if someone adds an
// eleventh leadership message later.
{
  const leadScope = loadGs(
    ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
     'CCSM_Agent1A.gs', 'CCSM_SeedContent.gs', 'CCSM_Agent1C.gs'],
    makeGasEnv().globals
  );
  const lead = leadScope._LEADERSHIP_MSGS;
  assert.ok(Array.isArray(lead) && lead.length > 0, '_LEADERSHIP_MSGS must be a non-empty array');

  assert.ok(/MENSAJES DE LIDERAZGO/.test(reviewMd),
    'CONTENT_REVIEW.md must contain the leadership-messages section');

  lead.forEach((m) => {
    if (!m.scripture) return;
    assert.ok(reviewMd.indexOf(m.scripture) !== -1,
      'CONTENT_REVIEW.md must list leadership scripture reference "' + m.scripture +
      '" so a human actually reviews it');
  });

  // Any leadership message shipping pre-written scripture text must be flagged
  // for verification — never presented as if it had cleared the same
  // no-fabrication gate as the 193 bank rows.
  if (lead.some((m) => m.scriptText)) {
    assert.ok(/requieren verificaci/i.test(reviewMd),
      'leadership messages carrying pre-written scripture text must be flagged for verification ' +
      'in CONTENT_REVIEW.md');
  }
}

console.log('seed content OK — ' + mb.rows.length + ' MESSAGE_BANK rows, ' + kb.rows.length +
  ' KNOWLEDGE_BASE rows, leadership messages listed');
