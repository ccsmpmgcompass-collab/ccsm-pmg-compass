// test_agent_scores_qa.js — CCSM_AgentScores.gs + CCSM_AgentQA.gs +
// CCSM_AgentValidation.gs + CCSM_AgentTestMode.gs.
//
// Four independent scenarios:
//   (a) Scores      — seed a week of DAILY_LOG (via CCSM_Agent3.gs) + WEEKLY_KI
//       (via CCSM_Agent5A.gs), run setupCcsmScoreConfig() then runAgentScores(),
//       assert SCORES gains one row per area with all four score columns
//       present and within [0, 100] (the scale asc_computeScore actually
//       produces — see CCSM_AgentScores.gs).
//   (b) QA          — stub geminiResponse, submit a test question, assert the
//       outbound Gemini request body contains 'Responda siempre en español'.
//   (c) Validation  — an invalid numeric field must be flagged
//       VALIDATION_ERROR and emailed BEFORE CCSM_AgentDuplicate.gs's
//       onNightlyFormSubmit runs its duplicate scan (the TODO CCSM_AgentDuplicate.gs
//       carried since Task 10, now restored).
//   (d) TestMode    — the 4 TEST_MODE functions have migrated out of
//       CCSM_Helpers.gs into CCSM_AgentTestMode.gs (see the acceptance greps
//       in the task brief).
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, addWeeklyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

function ymd(d) {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}

// ===========================================================================
// (a) SCORES — CCSM_AgentScores.gs
// ===========================================================================
(function testScores() {
  const env = makeGasEnv();
  const scope = loadGs(
    ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
     'CCSM_Agent3.gs', 'CCSM_Agent5A.gs', 'CCSM_AgentScores.gs'],
    env.globals
  );
  const ss = makeCcsmSpreadsheet(env, scope);

  setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');

  // Most recently COMPLETED Mon-Sun week — matches CCSM_AgentScores.gs's own
  // asc_getCurrentWeekRange() (same pattern used in test_agent1c.js).
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const sunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - today.getDay());
  const monday = new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() - 6);
  const weekDates = [];
  for (let i = 0; i < 7; i++) {
    weekDates.push(ymd(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i)));
  }

  // Seed a full week of nightly submissions for 'Arauco 1' (zone Arauco) —
  // covers every Effort-component key, every Skill-component rate's num/den
  // key, and a Todo effort answer.
  addNightlyRaw(env, ss, weekDates.map((d) => ({
    zone: 'Arauco', area: 'Arauco 1', report_date: d,
    roleplays: 2, contacts_attempted: 8, contacts_made: 5, meaningful_conversations: 3,
    friend_lessons: 2, baptismal_invitations: 1, member_contacts: 3, effort: 'Todo',
  })));
  scope.runAgent3(); // populates DAILY_LOG from NIGHTLY_FORM_RAW

  // One WEEKLY_FORM_RAW submission (Real/Meta KI values) for the same
  // area/week; runAgent5A() turns it into a WEEKLY_KI row.
  addWeeklyRaw(env, ss, [{
    zone: 'Arauco', area: 'Arauco 1', report_date: weekDates[6],
    leader_call: 'Sí', correlation_meeting: 'Sí',
    ki_new_people_real: 5, ki_new_people_meta: 5,
    ki_member_lessons_real: 3, ki_member_lessons_meta: 4,
    ki_friends_sacrament_real: 2, ki_friends_sacrament_meta: 3,
    ki_friends_first_week_real: 1, ki_friends_first_week_meta: 2,
    ki_baptismal_date_real: 1, ki_baptismal_date_meta: 1,
    ki_baptized_confirmed_real: 0, ki_baptized_confirmed_meta: 1,
    ki_rc_at_church_real: 2, ki_rc_at_church_meta: 2,
  }]);
  scope.runAgent5A(); // populates WEEKLY_KI

  scope.setupCcsmScoreConfig();
  scope.runAgentScores();

  const scores = ss.getSheetByName('SCORES').getDataRange().getValues();
  const headers = scores[0];
  ['Effort_Score', 'Skill_Score', 'KI_Score', 'Effectiveness_Score'].forEach((h) => {
    assert.ok(headers.indexOf(h) !== -1, 'SCORES must have a ' + h + ' column');
  });
  const col = (name) => headers.indexOf(name);
  const row = scores.slice(1).find(
    (r) => r[col('Area_Name')] === 'Arauco 1' && r[col('Week_Ending_Date')] === weekDates[6]
  );
  assert.ok(row, 'expected a SCORES row for Arauco 1 / ' + weekDates[6] + ' — got rows: ' + JSON.stringify(scores.slice(1)));

  ['Effort_Score', 'Skill_Score', 'KI_Score', 'Effectiveness_Score'].forEach((h) => {
    const v = row[col(h)];
    assert.strictEqual(typeof v, 'number', h + ' must be numeric, got ' + typeof v);
    assert.ok(v >= 0 && v <= 100, h + ' must be in [0, 100], got ' + v);
  });
  // With full-goal-attainment fixture data (or better), scores should be
  // meaningfully above zero, not structurally zero.
  assert.ok(row[col('Effort_Score')] > 0, 'Effort_Score must be > 0 for a fully-submitting area');
  assert.ok(row[col('Skill_Score')] > 0, 'Skill_Score must be > 0 for a fully-submitting area');
  assert.ok(row[col('KI_Score')] > 0, 'KI_Score must be > 0 when Real values are seeded');

  // Re-running must REPLACE, not duplicate, this week's row.
  scope.runAgentScores();
  const scores2 = ss.getSheetByName('SCORES').getDataRange().getValues();
  const matches = scores2.slice(1).filter(
    (r) => r[col('Area_Name')] === 'Arauco 1' && r[col('Week_Ending_Date')] === weekDates[6]
  );
  assert.strictEqual(matches.length, 1, 're-running runAgentScores() must replace, not duplicate, the week\'s row');

  console.log('agentScores OK');
})();

// ===========================================================================
// (b) QA — CCSM_AgentQA.gs (Spanish Gemini prompt)
// ===========================================================================
(function testQA() {
  const geminiEnvelope = JSON.stringify({
    candidates: [{ content: { parts: [{ text: JSON.stringify({
      answer: 'Debe completar el formulario nocturno cada noche antes de la planificación.',
      confidence: 9,
      reasoning: 'kb-001 responde directamente la pregunta.',
      matchedIds: ['kb-001'],
    }) }] } }],
  });
  const geminiResponse = { getResponseCode: () => 200, getContentText: () => geminiEnvelope };
  const env = makeGasEnv({ geminiResponse });

  // gas_stubs.js's UrlFetchApp.fetch stub returns options.geminiResponse
  // verbatim for every call but does not itself record request payloads —
  // wrap it here so this test can inspect the outbound request body.
  const capturedRequests = [];
  const originalFetch = env.globals.UrlFetchApp.fetch;
  env.globals.UrlFetchApp.fetch = function(url, params) {
    capturedRequests.push({ url, params });
    return originalFetch(url, params);
  };

  const scope = loadGs(
    ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs', 'CCSM_AgentQA.gs'],
    env.globals
  );
  const ss = makeCcsmSpreadsheet(env, scope);
  env.globals.PropertiesService.getScriptProperties().setProperty('GEMINI_API_KEY', 'test-key');

  // Seed one KNOWLEDGE_BASE row (CCSM_AgentQA.gs deliberately does not port
  // Provo's Drive-JSON setupKnowledgeBase() — Task 13 seeds real content —
  // so seed directly here).
  const kbSheet = ss.getSheetByName('KNOWLEDGE_BASE');
  kbSheet.appendRow(['kb-001', 'Formulario Nocturno', '¿Cuándo debo completar el formulario nocturno?',
    'Complete el formulario nocturno cada noche antes de la planificación del día siguiente.',
    'formulario, nocturno', 'TEST', '2026-01-01', 0]);

  scope.onQAFormSubmit({ values: [
    new Date(), 'Pregunta', '', '', '',
    'Elder Test', 'elder.test@missionary.org', '¿Cuándo debo completar el formulario nocturno?',
  ] });

  assert.ok(capturedRequests.length >= 1, 'expected at least one Gemini request');
  const body = capturedRequests[0].params.payload;
  assert.ok(/Responda siempre en español/.test(body),
    'outbound Gemini request must carry the required Spanish system-prompt prefix: ' + body.substring(0, 200));
  assert.ok(body.indexOf(scope.getMissionName()) !== -1,
    'outbound Gemini request must name the mission');

  // The confident answer (confidence=9) must be emailed to the missionary,
  // redirected to the TEST inbox per TEST_MODE.
  assert.strictEqual(env.state.emails.length, 1, 'expected exactly one answer email');
  assert.strictEqual(env.state.emails[0].to, 'CCSM.PMG.Compass@gmail.com', 'TEST_MODE must redirect to the test inbox');
  assert.ok(env.state.emails[0].subject.indexOf('[TEST]') === 0, 'subject must carry the [TEST] prefix');

  console.log('agentQA OK');
})();

// ===========================================================================
// (c) VALIDATION — CCSM_AgentValidation.gs, wired into CCSM_AgentDuplicate.gs
// ===========================================================================
(function testValidation() {
  const env = makeGasEnv();
  const scope = loadGs(
    ['CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
     'CCSM_AgentValidation.gs', 'CCSM_AgentDuplicate.gs'],
    env.globals
  );
  const ss = makeCcsmSpreadsheet(env, scope);

  function setMissionOrgField(areaName, header, value) {
    const sheet = ss.getSheetByName('MISSION_ORG');
    const data = sheet.getDataRange().getValues();
    const headers = data[0];
    const colIdx = headers.indexOf(header);
    const areaIdx = headers.indexOf('Area_Name');
    for (let i = 1; i < data.length; i++) {
      if (data[i][areaIdx] === areaName) { sheet.getRange(i + 1, colIdx + 1).setValue(value); return; }
    }
    throw new Error('setMissionOrgField: area not found: ' + areaName);
  }
  setMissionOrgField('Arauco 1', 'Companion1_Email', 'arauco1.companion@missionary.org');

  // Invalid roleplays value ('abc', not a non-negative integer) must be
  // caught BEFORE CCSM_AgentDuplicate's duplicate scan runs.
  addNightlyRaw(env, ss, [
    { zone: 'Arauco', area: 'Arauco 1', report_date: '2026-07-10', exchanges: 'Sí', roleplays: 'abc' },
  ]);

  scope.onNightlyFormSubmit();

  const rows = ss.getSheetByName('NIGHTLY_FORM_RAW').getDataRange().getValues();
  const headers = rows[0];
  const statusCol = headers.indexOf('STATUS');
  assert.ok(statusCol !== -1, 'expected a STATUS column to be added to NIGHTLY_FORM_RAW');
  assert.strictEqual(rows[1][statusCol], 'VALIDATION_ERROR', 'invalid roleplays value must be flagged VALIDATION_ERROR');

  assert.strictEqual(env.state.emails.length, 1, 'expected exactly one resubmission-request email');
  const badEmail = env.state.emails[0];
  assert.strictEqual(badEmail.to, 'CCSM.PMG.Compass@gmail.com', 'TEST_MODE must redirect to the test inbox');
  assert.ok(/reenv/i.test(badEmail.subject), 'subject must be the Spanish resubmission request: ' + badEmail.subject);
  assert.ok(/Arauco 1/.test(badEmail.htmlBody || badEmail.body), 'body must reference the area');

  // No AgentDuplicate run-log row: onNightlyFormSubmit must have returned
  // BEFORE reaching the duplicate scan / its own logRun() call.
  const runLog = ss.getSheetByName('AGENT_RUN_LOG').getDataRange().getValues();
  const runLogHeaders = runLog[0];
  const agentCol = runLogHeaders.indexOf('Agent');
  assert.ok(!runLog.some((r) => r[agentCol] === 'AgentDuplicate'),
    'AgentDuplicate must not have run its duplicate scan on a row that failed validation');

  console.log('agentValidation OK');
})();

// ===========================================================================
// (d) TESTMODE — CCSM_AgentTestMode.gs defines the 4 functions; CCSM_Helpers.gs
// no longer carries the temporary copies (acceptance greps from the task brief).
// ===========================================================================
(function testTestMode() {
  const helpersSrc = require('fs').readFileSync('CCSM_Helpers.gs', 'utf8');
  const tempCount = (helpersSrc.match(/function (isTestMode|getTestInbox|resolveRecipient|resolveSubject)\(/g) || []).length;
  assert.strictEqual(tempCount, 0, 'CCSM_Helpers.gs must no longer define the 4 temporary TestMode functions');

  const testModeSrc = require('fs').readFileSync('CCSM_AgentTestMode.gs', 'utf8');
  const definedCount = (testModeSrc.match(/function (isTestMode|getTestInbox|resolveRecipient|resolveSubject)\(/g) || []).length;
  assert.strictEqual(definedCount, 4, 'CCSM_AgentTestMode.gs must define all 4 TestMode functions');

  console.log('agentTestMode OK');
})();

// ===========================================================================
// No Provo residue in any of the four forked files
// ===========================================================================
['CCSM_AgentScores.gs', 'CCSM_AgentQA.gs', 'CCSM_AgentValidation.gs', 'CCSM_AgentTestMode.gs'].forEach((file) => {
  const src = require('fs').readFileSync(file, 'utf8');
  assert.ok(!/Utah Provo/i.test(src), file + ' must not contain "Utah Provo"');
  assert.ok(!/America\/Denver/.test(src), file + ' must not contain "America/Denver"');
});

console.log('agent scores/qa/validation/testmode OK');
