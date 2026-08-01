// test_full_pipeline.js — the FIRST time every CCSM_*.gs file runs together.
//
// Every other tests/test_*.js loads a small subset of agents and exercises it
// against fixtures. This one loads ALL of them (plus CcsmData + the sheet
// builder + CCSM_Setup.gs) into ONE env, builds COMPASS_CCSM from scratch,
// seeds the real Spanish MESSAGE_BANK / KNOWLEDGE_BASE content, attaches
// fixture raw form tabs, simulates a week of submissions for three areas with
// three different behaviours, and then runs the agents IN THE ORDER THE
// PROJECT TRIGGER SCHEDULE (CCSM_Setup.gs) fires them.
//
//   "Arauco 1"  (zone Arauco)     — perfect: submits every simulated day and
//                                   the weekly form.
//   "Arauco 2"  (zone Arauco)     — gap: submits every simulated day EXCEPT
//                                   the two days before today, and never
//                                   submits the weekly form.
//   "San Pedro" (zone San Pedro)  — duplicate: submits every simulated day,
//                                   and submits the FIRST simulated day twice
//                                   (identical area+date) plus the weekly form.
//
// WALL-CLOCK INDEPENDENCE (this suite must pass on any day of the week —
// several agents key off the real clock and cannot be frozen):
//   * "today" is derived by formatting new Date() through
//     getMissionTimezone() and re-parsing the yyyy-MM-dd — the same idiom the
//     agents use — so the suite is independent of the DEV MACHINE's timezone
//     and time of day as well as of the calendar date.
//   * The simulated window runs from the Monday of the most recently
//     COMPLETED Mon–Sun week through today, inclusive. That window always
//     fully contains the week Agent1A / AgentScores analyse (they both derive
//     "most recent Sunday" from the real clock), AND always contains
//     today-1 / today-2. On a Monday the window is exactly 8 days, matching
//     the brief's "8 days"; on other weekdays it is 7–13 days.
//   * MISSED_DAYS_LOOKBACK is set to 2 and the gap area is missing exactly
//     today-1 and today-2 — so the missing set is ALWAYS those two days,
//     always consecutive, on every possible run date. That trips Agent3's
//     Tier-1 companionship reminder (2+ consecutive) and never its Tier-2 DL
//     escalation (needs 3+), deterministically.
//   * ar_checkWeeklyCompliance's Mon/Tue 8 AM–9 PM gate is bypassed with the
//     established runReminderAgent({skipTimeGate:true}) option; System 2's
//     Mon–Wed stage gate is bypassed with runWeeklyEscalation({forceStage:N}).
//     Neither bypass exists on the production (zero-argument) code path.
//   * No assertion below compares against a hardcoded calendar date.
const { makeGasEnv } = require('./gas_stubs');
const { loadGs } = require('./load_gs');
const { makeCcsmSpreadsheet, addNightlyRaw, addWeeklyRaw, setConfig } = require('./fixtures');
const assert = require('assert');

const TEST_INBOX = 'CCSM.PMG.Compass@gmail.com';

// Every CCSM file, loaded into one shared scope — exactly what the Apps
// Script project does.
const GS_FILES = [
  'CcsmData.gs', 'BuildCcsmSheet.gs', 'CCSM_Helpers.gs', 'CCSM_AgentTestMode.gs',
  'CCSM_Agent1A.gs', 'CCSM_Agent1B.gs', 'CCSM_Agent1C.gs', 'CCSM_Agent2.gs',
  'CCSM_Agent3.gs', 'CCSM_Agent4.gs', 'CCSM_Agent5A.gs', 'CCSM_Agent5B.gs',
  'CCSM_Agent6.gs', 'CCSM_AgentDuplicate.gs', 'CCSM_AgentEscalation.gs',
  'CCSM_AgentQA.gs', 'CCSM_AgentReminder.gs', 'CCSM_AgentScores.gs',
  'CCSM_AgentValidation.gs', 'CCSM_SeedContent.gs', 'CCSM_Setup.gs',
];

// ---------------------------------------------------------------------------
// Date helpers — all local-calendar, matching every agent's own yyyy-MM-dd
// string handling.
// ---------------------------------------------------------------------------
function ymd(d) {
  return d.getFullYear() + '-' +
    String(d.getMonth() + 1).padStart(2, '0') + '-' +
    String(d.getDate()).padStart(2, '0');
}
function addDays(d, n) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

// Gemini envelope: CCSM_Helpers.callGemini() expects a real Gemini HTTP
// response object; Agent1C's batch-narrative call then expects the text
// payload to be a JSON map of unit name -> Spanish narrative. Both zones the
// simulated areas belong to are answered.
const geminiEnvelope = JSON.stringify({
  candidates: [{ content: { parts: [{ text: JSON.stringify({
    'Arauco': 'Narrativa de prueba para la zona Arauco: buen contacto y esfuerzo constante esta semana.',
    'San Pedro': 'Narrativa de prueba para la zona San Pedro: constancia en los informes esta semana.',
  }) }] } }],
});
const geminiResponse = {
  getResponseCode: () => 200,
  getContentText: () => geminiEnvelope,
};

// ===========================================================================
// PHASE 0 — build the sheet exactly the way a new mission would
// ===========================================================================
const env = makeGasEnv({ geminiResponse });
const scope = loadGs(GS_FILES, env.globals);
const ss = makeCcsmSpreadsheet(env, scope);

setConfig(env, ss, 'SYSTEM_START_DATE', '2020-01-01');
setConfig(env, ss, 'TRANSFER_START_DATE', '2020-01-01');
setConfig(env, ss, 'NIGHTLY_FORM_LINK', 'https://forms.example/nightly');
setConfig(env, ss, 'WEEKLY_FORM_LINK', 'https://forms.example/weekly');
// See the wall-clock note in the file header: exactly the two days the gap
// area is missing.
setConfig(env, ss, 'MISSED_DAYS_LOOKBACK', '2');
// Agent5B/Agent6 qualification threshold — a weekly goal the perfect area
// clears on the Mon–Thu days it has data for.
setConfig(env, ss, 'GOAL_new_people_found', '3');

// ---------------------------------------------------------------------------
// "Today", anchored to the MISSION timezone — NOT to Node's local clock.
//
// Every agent that keys off the real clock derives its date by formatting
// new Date() through getMissionTimezone() and parsing the yyyy-MM-dd back as
// a local calendar date (CCSM_AgentScores.gs:437-440, CCSM_Agent1A.gs:110-113).
// Deriving the test's date any other way makes the suite pass only when the
// dev machine's calendar date happens to equal Santiago's — it fails in the
// rollover window (e.g. a Saturday 22:30 in America/Denver is already Sunday
// in Santiago). The idiom below is a verbatim copy of the agents'.
//
// It must run AFTER the setConfig() block above: getMissionTimezone() goes
// through readAgentConfig(), which memoises the whole AGENT_CONFIG map for the
// execution, and the fixture setConfig() writes the sheet without busting that
// cache. Reading config any earlier freezes the pre-setConfig values.
// ---------------------------------------------------------------------------
// Node's LOCAL calendar must equal the mission timezone before any date is
// derived. The agents freely mix two idioms: format-through-
// getMissionTimezone() (e.g. CCSM_AgentScores.gs:437) and plain local-calendar
// arithmetic on new Date(y, m, d) (e.g. CCSM_Agent5A.gs:888-896
// a5a_getWeekEnd). In the Apps Script runtime those agree, because the
// project's script timezone IS the mission timezone. Under Node they only
// agree if the process's local timezone is the mission's — otherwise a machine
// east of Santiago turns local-midnight Sunday into Saturday 20:00 Santiago
// and week-ends slip a day.
//
// gas_stubs.js pins process.env.TZ to a hardcoded MISSION_TZ at require()
// time. The sheet's AGENT_CONFIG carries the mission timezone independently,
// so the two can disagree — on a fork to another mission, or under
// CCSM_TEST_TZ_PIN=0. Assert they agree BEFORE deriving any date: a silent
// disagreement is what slips every derived week-end by a day.
const missionTz = scope.getMissionTimezone();
assert.ok(missionTz, 'AGENT_CONFIG must define MISSION_TIMEZONE');
assert.strictEqual(process.env.TZ, missionTz,
  "gas_stubs.js's process timezone pin must equal AGENT_CONFIG MISSION_TIMEZONE " +
  '(a fork changes the config; the pin has to follow, and CCSM_TEST_TZ_PIN=0 ' +
  'is expected to trip this on a non-mission machine)');

const _tzNow = new Date();
const _todayStr = env.globals.Utilities.formatDate(_tzNow, scope.getMissionTimezone(), 'yyyy-MM-dd');
const _todayParts = _todayStr.split('-');
const today = new Date(
  parseInt(_todayParts[0], 10),
  parseInt(_todayParts[1], 10) - 1,
  parseInt(_todayParts[2], 10)
);
// Most recent Sunday (today if today is Sunday) and the Monday 6 days before
// it — the exact week Agent1A and AgentScores analyse.
const sunday = addDays(today, -today.getDay());
const monday = addDays(sunday, -6);

const weekEndStr = ymd(sunday);
const spanDays = Math.round((today - monday) / 86400000);
const simDates = [];
for (let i = 0; i <= spanDays; i++) simDates.push(ymd(addDays(monday, i)));

const gapDates = [ymd(addDays(today, -2)), ymd(addDays(today, -1))];
const dupDate = simDates[0];

// Seed content — this is the FIRST time either seeder runs against a real
// (in-memory) COMPASS_CCSM sheet rather than a unit fixture.
scope.seedCcsmMessageBank();
scope.seedCcsmKnowledgeBase();
scope.setupCcsmScoreConfig();

// Install the production trigger schedule. Agent4's CHECK 11 audits exactly
// this inventory, so the health check below runs against a realistic project.
scope.setupAllCcsmTriggers();

// ---------------------------------------------------------------------------
// Companion emails. MISSION_ORG ships with every email column blank, so an
// area only becomes reachable once one is set — which makes the recipient set
// of this whole run exactly these three areas.
// ---------------------------------------------------------------------------
function setMissionOrgField(areaName, header, value) {
  const sheet = ss.getSheetByName('MISSION_ORG');
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const colIdx = headers.indexOf(header);
  const areaIdx = headers.indexOf('Area_Name');
  for (let i = 1; i < data.length; i++) {
    if (data[i][areaIdx] === areaName) {
      sheet.getRange(i + 1, colIdx + 1).setValue(value);
      return;
    }
  }
  throw new Error('setMissionOrgField: area not found: ' + areaName);
}
setMissionOrgField('Arauco 1', 'Companion1_Email', 'arauco1@missionary.org');
setMissionOrgField('Arauco 2', 'Companion1_Email', 'arauco2@missionary.org');
setMissionOrgField('San Pedro', 'Companion1_Email', 'sanpedro@missionary.org');

// ===========================================================================
// PHASE 1 — attach the fixture raw tabs and simulate the week
// ===========================================================================
const nightlyRows = [];
simDates.forEach((d) => {
  nightlyRows.push({
    zone: 'Arauco', area: 'Arauco 1', report_date: d, exchanges: 'Sí', effort: 'Todo',
    roleplays: 2, contacts_attempted: 14, contacts_made: 7, meaningful_conversations: 3,
    new_people_found: 1, friend_lessons: 2, baptismal_invitations: 1, member_contacts: 3,
  });
  if (gapDates.indexOf(d) === -1) {
    nightlyRows.push({
      zone: 'Arauco', area: 'Arauco 2', report_date: d, exchanges: 'No', effort: 'Algo',
      roleplays: 1, contacts_attempted: 10, contacts_made: 4, new_people_found: 1,
    });
  }
  nightlyRows.push({
    zone: 'San Pedro', area: 'San Pedro', report_date: d, exchanges: 'Sí', effort: 'La mayor parte',
    roleplays: 1, contacts_attempted: 8, contacts_made: 5, new_people_found: 1,
  });
});
// The duplicate: San Pedro submits the first simulated day a SECOND time.
nightlyRows.push({
  zone: 'San Pedro', area: 'San Pedro', report_date: dupDate, exchanges: 'Sí',
  effort: 'La mayor parte', roleplays: 1, contacts_attempted: 8, contacts_made: 5,
  new_people_found: 1,
});
addNightlyRaw(env, ss, nightlyRows);

// Weekly form: the perfect area and the duplicate area submit; the gap area
// does NOT (it is the non-submitter the weekly reminder must reach).
addWeeklyRaw(env, ss, [
  { zone: 'Arauco', area: 'Arauco 1', report_date: weekEndStr,
    leader_call: 'Sí', correlation_meeting: 'Sí',
    ki_new_people_real: 5, ki_new_people_meta: 5,
    ki_member_lessons_real: 3, ki_member_lessons_meta: 4,
    ki_friends_sacrament_real: 2, ki_friends_sacrament_meta: 3,
    ki_friends_first_week_real: 1, ki_friends_first_week_meta: 2,
    ki_baptismal_date_real: 1, ki_baptismal_date_meta: 1,
    ki_baptized_confirmed_real: 0, ki_baptized_confirmed_meta: 1,
    ki_rc_at_church_real: 2, ki_rc_at_church_meta: 2 },
  { zone: 'San Pedro', area: 'San Pedro', report_date: weekEndStr,
    leader_call: 'Sí', correlation_meeting: 'No',
    ki_new_people_real: 2, ki_new_people_meta: 4,
    ki_member_lessons_real: 1, ki_member_lessons_meta: 2 },
]);

const nightlyRowsSeeded = ss.getSheetByName('NIGHTLY_FORM_RAW').getDataRange().getValues().length - 1;
assert.strictEqual(nightlyRowsSeeded, nightlyRows.length,
  'fixture seeding must land every simulated nightly row');

// ===========================================================================
// PHASE 2 — run the agents in project-trigger-schedule order
// ===========================================================================
// Daily cycle (Santiago local time):
//   06:00 runAgent3 | 07:00 runAgentEscalation | 21:00 runAgent3Evening
//   21:30 runAgentDuplicate
scope.runAgent3();
scope.runAgentEscalation();
scope.runAgent3Evening();
scope.runAgentDuplicate();

// Sunday: 18:00 runAgentReminder | 22:00 runAgent5A
scope.runAgentReminder();
scope.runAgent5A();

// Monday: 00:05 runAgentScores | 07:00 runAgent4 | 21:30 runAgent1A (chains 1B -> 1C)
scope.runAgentScores();
scope.runAgent4();
scope.runAgent1A();
scope.runAgent1B();   // chained by runAgent1A via scheduleNext(); the stub
scope.runAgent1C();   // never fires triggers, so the chain is driven here.

// Friday: 12:00 runAgent5B (chains Agent6)
scope.runAgent5B();
scope.runAgent6();

// The FOLLOWING Monday 07:00 — runAgent4 again. Agent4 is weekly, and on the
// first Monday of a brand-new sheet several tabs it audits (notably
// ENCOURAGEMENT_HISTORY, which only Agent6 populates, on Fridays) have never
// been written, so that first run legitimately reports WARN. Running it once
// more after a complete Sun->Mon->Fri cycle is what a real mission's second
// week looks like, and asserts the health check actually reaches a clean
// SUCCESS rather than sitting on a permanent warning.
scope.runAgent4();

// ===========================================================================
// PHASE 3 — assertions
// ===========================================================================

// --- DAILY_LOG -------------------------------------------------------------
const dailyLog = ss.getSheetByName('DAILY_LOG').getDataRange().getValues();
const dlH = dailyLog[0];
const dlDate = dlH.indexOf('Date');
const dlArea = dlH.indexOf('Area');
const dlRows = (area) => dailyLog.slice(1).filter((r) => r[dlArea] === area);

assert.strictEqual(dlRows('Arauco 1').length, simDates.length,
  'perfect area must have one DAILY_LOG row per simulated day');
assert.strictEqual(dlRows('Arauco 2').length, simDates.length - gapDates.length,
  'gap area must be missing exactly the two skipped days in DAILY_LOG');
assert.strictEqual(dlRows('San Pedro').length, simDates.length,
  'duplicate-submitting area must have ONE DAILY_LOG row per day, not two for the duplicated date');

gapDates.forEach((d) => {
  assert.ok(!dlRows('Arauco 2').some((r) => r[dlDate] === d),
    'gap area must have no DAILY_LOG row for ' + d);
});

// The duplicated date was SUMMED by Agent3 (06:00) before AgentDuplicate
// (21:30) deleted the raw rows — order-dependent, and the whole point of
// running the schedule in order.
const dupRow = dlRows('San Pedro').find((r) => r[dlDate] === dupDate);
assert.ok(dupRow, 'expected a DAILY_LOG row for the duplicated date');
assert.strictEqual(dupRow[dlH.indexOf('contacts_attempted')], 16,
  'Agent3 must sum the two same-day San Pedro submissions (8 + 8) before AgentDuplicate deletes them');
assert.strictEqual(dlRows('Arauco 1')[0][dlH.indexOf('exchanges')], 'TRUE',
  'Sí must normalize to TRUE in DAILY_LOG');

console.log('pipeline DAILY_LOG OK');

// --- Duplicate flagged, raw rows removed -----------------------------------
const rawAfter = ss.getSheetByName('NIGHTLY_FORM_RAW').getDataRange().getValues().length - 1;
assert.strictEqual(rawAfter, nightlyRows.length - 2,
  'AgentDuplicate must delete BOTH rows of the duplicate group');

const runLog = ss.getSheetByName('AGENT_RUN_LOG').getDataRange().getValues();
const rlH = runLog[0];
const rlAgent = rlH.indexOf('Agent');
const rlStatus = rlH.indexOf('Status');
const rlNotes = rlH.indexOf('Notes');

// AGENT_RUN_LOG records THAT the sweep ran...
const dupLogRow = runLog.slice(1).find(
  (r) => r[rlAgent] === 'AgentDuplicate' && /duplicate group\(s\) resolved/.test(String(r[rlNotes]))
);
assert.ok(dupLogRow, 'AgentDuplicate must record the resolved duplicate group in AGENT_RUN_LOG');

// ...and AUDIT_LOG records WHICH area and date it flagged. That per-event row
// is what answers "why does this area show 16 contacts instead of 8?" —
// AGENT_RUN_LOG cannot, it is a run record. Column layout is the one every
// other CCSM agent writes:
//   Timestamp | Agent | Action | Rows_Affected | Area | Notes
const auditLog = ss.getSheetByName('AUDIT_LOG').getDataRange().getValues();
const alRows = auditLog.filter((r) => String(r[1]) === 'AgentDuplicate');
assert.strictEqual(alRows.length, 1,
  'AgentDuplicate must write exactly one AUDIT_LOG row (one per duplicate group flagged), got ' +
  alRows.length);
const alRow = alRows[0];
assert.strictEqual(String(alRow[2]), 'DUPLICATE_RESOLVED', 'AUDIT_LOG Action column');
assert.strictEqual(Number(alRow[3]), 2, 'AUDIT_LOG Rows_Affected must be the 2 deleted raw rows');
assert.strictEqual(String(alRow[4]), 'San Pedro', 'AUDIT_LOG Area must name the flagged area');
assert.ok(String(alRow[5]).indexOf(dupDate) !== -1,
  'AUDIT_LOG Notes must name the flagged date ' + dupDate + ', got: ' + alRow[5]);
assert.ok(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(String(alRow[0])),
  'AUDIT_LOG Timestamp must be mission-tz yyyy-MM-dd HH:mm:ss, got: ' + alRow[0]);

console.log('pipeline duplicate handling OK');

// --- WEEKLY_KI -------------------------------------------------------------
const ki = ss.getSheetByName('WEEKLY_KI').getDataRange().getValues();
const kiH = ki[0];
const kiArea = kiH.indexOf('Area');
assert.deepStrictEqual(kiH.slice(0, 4), ['Week_End_Date', 'Area', 'Zone', 'District']);
assert.strictEqual(ki.length - 1, 2, 'expected exactly 2 WEEKLY_KI rows (the two weekly submitters)');

const kiArauco1 = ki.slice(1).find((r) => r[kiArea] === 'Arauco 1');
assert.ok(kiArauco1, 'expected a WEEKLY_KI row for the perfect area');
assert.strictEqual(kiArauco1[kiH.indexOf('Week_End_Date')], weekEndStr);
assert.strictEqual(kiArauco1[kiH.indexOf('ki_new_people_real')], 5);
assert.strictEqual(kiArauco1[kiH.indexOf('ki_new_people_meta')], 5);
assert.strictEqual(kiArauco1[kiH.indexOf('leader_call')], 'TRUE');
assert.ok(!ki.slice(1).some((r) => r[kiArea] === 'Arauco 2'),
  'the non-submitting area must NOT appear in WEEKLY_KI');

console.log('pipeline WEEKLY_KI OK');

// --- SCORES ----------------------------------------------------------------
const scores = ss.getSheetByName('SCORES').getDataRange().getValues();
const scH = scores[0];
const scCol = (n) => scH.indexOf(n);
const scoreRow = scores.slice(1).find(
  (r) => r[scCol('Area_Name')] === 'Arauco 1' && r[scCol('Week_Ending_Date')] === weekEndStr
);
assert.ok(scoreRow, 'expected a SCORES row for the perfect area / ' + weekEndStr);
['Effort_Score', 'Skill_Score', 'KI_Score', 'Effectiveness_Score'].forEach((h) => {
  const v = scoreRow[scCol(h)];
  assert.strictEqual(typeof v, 'number', h + ' must be numeric');
  assert.ok(v >= 0 && v <= 100, h + ' must be in [0, 100], got ' + v);
});
assert.ok(scoreRow[scCol('Effort_Score')] > 0,
  'Effort_Score must be > 0 for an area that submitted every day');

console.log('pipeline SCORES OK');

// --- Missed-days alert for the gap area ------------------------------------
const missedAlerts = env.state.emails.filter(
  (e) => /Arauco 2/.test((e.htmlBody || e.body || '') + e.subject) &&
         /Informe/.test(e.subject)
);
assert.ok(missedAlerts.length > 0, 'the gap area must receive a missed-days alert');

const missingLog = ss.getSheetByName('MISSING_LOG').getDataRange().getValues();
const mlH = missingLog[0];
const mlArea = mlH.indexOf('Area');
const mlDates = mlH.indexOf('Missing_Dates');
const mlRow = missingLog.slice(1).find((r) => r[mlArea] === 'Arauco 2');
assert.ok(mlRow, 'MISSING_LOG must record the gap area');
assert.strictEqual(String(mlRow[mlDates]), gapDates.join(','),
  'MISSING_LOG must record exactly the two skipped days');
assert.ok(!missingLog.slice(1).some((r) => r[mlArea] === 'Arauco 1'),
  'the perfect area must never appear in MISSING_LOG');

console.log('pipeline missed-days OK');

// --- Coaching emails: Spanish, TEST inbox ----------------------------------
const coaching = env.state.emails.filter((e) => /Entrenamiento Semanal/.test(e.subject));
assert.ok(coaching.length > 0, 'expected at least one Sunday coaching email from Agent1C');
coaching.forEach((e) => {
  assert.strictEqual(e.to, TEST_INBOX, 'coaching email must be redirected to the TEST inbox');
  const body = e.htmlBody || e.body || '';
  assert.ok(/Fortaleza|Oportunidad|Resumen/.test(body),
    'coaching body must be Spanish: ' + e.subject);
  assert.ok(!/Growth Focus|Week ending|Mission Summary|Strength/.test(body),
    'coaching body must not leak English: ' + e.subject);
});

const wb = ss.getSheetByName('WEEKLY_BREAKDOWNS').getDataRange().getValues();
assert.ok(wb.length > 1, 'Agent1C must write WEEKLY_BREAKDOWNS rows');

console.log('pipeline coaching OK');

// --- AGENT_RUN_LOG: one SUCCESS row per agent run --------------------------
const EXPECTED_AGENT_RUNS = [
  'Agent3', 'AgentEscalation', 'AgentDuplicate', 'AgentReminder',
  'Agent1A', 'Agent1B', 'Agent1C', 'Agent5A', 'AgentScores', 'Agent4',
  'Agent5B', 'Agent6',
];
EXPECTED_AGENT_RUNS.forEach((agent) => {
  const rows = runLog.slice(1).filter((r) => r[rlAgent] === agent);
  assert.ok(rows.length > 0, 'AGENT_RUN_LOG must have a row for ' + agent);
  assert.ok(
    rows.some((r) => String(r[rlStatus]) === 'SUCCESS'),
    'AGENT_RUN_LOG must have a SUCCESS row for ' + agent + ' — got ' +
    rows.map((r) => r[rlStatus] + ': ' + r[rlNotes]).join(' || ')
  );
});

console.log('pipeline AGENT_RUN_LOG OK');

// --- TEST_MODE routing: every single email went to the test inbox ----------
assert.ok(env.state.emails.length > 0, 'the simulated week must have produced emails');
assert.ok(
  env.state.emails.every((e) => e.to === TEST_INBOX),
  'TEST_MODE must redirect EVERY email to ' + TEST_INBOX + ' — leaked: ' +
  JSON.stringify(env.state.emails.filter((e) => e.to !== TEST_INBOX).map((e) => e.to))
);
assert.ok(
  env.state.emails.every((e) => String(e.subject).indexOf('[TEST] ') === 0),
  'TEST_MODE must prefix every subject with [TEST]'
);
// The recipient addresses seeded on MISSION_ORG must never appear in a `to`.
['arauco1@missionary.org', 'arauco2@missionary.org', 'sanpedro@missionary.org'].forEach((addr) => {
  assert.ok(!env.state.emails.some((e) => String(e.to).indexOf(addr) !== -1),
    'real missionary address ' + addr + ' must never be a live recipient in TEST_MODE');
});

console.log('pipeline TEST_MODE routing OK (' + env.state.emails.length + ' emails)');

// ===========================================================================
// NEGATIVE CONTROL — prove the TEST_MODE assertion above is not vacuous.
// Same build, TEST_MODE = FALSE: the very same agent must then address the
// real missionary, which is exactly what the assertion above would catch.
// ===========================================================================
{
  const ctlEnv = makeGasEnv();
  const ctlScope = loadGs(GS_FILES, ctlEnv.globals);
  const ctlSs = makeCcsmSpreadsheet(ctlEnv, ctlScope);
  setConfig(ctlEnv, ctlSs, 'TEST_MODE', 'FALSE');
  setConfig(ctlEnv, ctlSs, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(ctlEnv, ctlSs, 'WEEKLY_FORM_LINK', 'https://forms.example/weekly');
  setConfig(ctlEnv, ctlSs, 'WEEKLY_REMINDER_OWNER', 'AGENT_REMINDER');
  addWeeklyRaw(ctlEnv, ctlSs, []);

  const ctlOrg = ctlSs.getSheetByName('MISSION_ORG');
  const ctlData = ctlOrg.getDataRange().getValues();
  const ctlAreaIdx = ctlData[0].indexOf('Area_Name');
  const ctlEmailIdx = ctlData[0].indexOf('Companion1_Email');
  for (let i = 1; i < ctlData.length; i++) {
    if (ctlData[i][ctlAreaIdx] === 'Arauco 2') {
      ctlOrg.getRange(i + 1, ctlEmailIdx + 1).setValue('arauco2@missionary.org');
      break;
    }
  }

  ctlScope.runReminderAgent({ skipTimeGate: true });
  assert.ok(ctlEnv.state.emails.length > 0, 'negative control must produce an email');
  assert.ok(
    ctlEnv.state.emails.some((e) => e.to === 'arauco2@missionary.org'),
    'with TEST_MODE=FALSE the reminder must address the real missionary — proving the ' +
    'TEST_MODE assertion above actually discriminates'
  );
  assert.ok(
    !ctlEnv.state.emails.every((e) => e.to === TEST_INBOX),
    'negative control must FAIL the every()-to-test-inbox predicate'
  );
  console.log('pipeline TEST_MODE negative control OK');
}

// ===========================================================================
// OVERLAP GATE — CCSM_Setup.gs's WEEKLY_REMINDER_OWNER deployment decision.
//
// AgentReminder's weekly-compliance half and AgentEscalation's System 2 both
// email non-submitting companionships about the weekly form, with the SAME
// Spanish subject. Running both live double-nags every area. WEEKLY_REMINDER_OWNER
// selects exactly one owner; the shipped default is AGENT_ESCALATION.
//
// Both time gates are bypassed here so the assertion holds on ANY weekday.
// ===========================================================================
function makeReminderEnv(owner) {
  const e = makeGasEnv();
  const s = loadGs(GS_FILES, e.globals);
  const sheet = makeCcsmSpreadsheet(e, s);
  setConfig(e, sheet, 'SYSTEM_START_DATE', '2020-01-01');
  setConfig(e, sheet, 'WEEKLY_FORM_LINK', 'https://forms.example/weekly');
  if (owner !== undefined) setConfig(e, sheet, 'WEEKLY_REMINDER_OWNER', owner);
  addWeeklyRaw(e, sheet, []); // tab exists, zero submissions

  const org = sheet.getSheetByName('MISSION_ORG');
  const data = org.getDataRange().getValues();
  const aIdx = data[0].indexOf('Area_Name');
  const eIdx = data[0].indexOf('Companion1_Email');
  for (let i = 1; i < data.length; i++) {
    if (data[i][aIdx] === 'Arauco 2') {
      org.getRange(i + 1, eIdx + 1).setValue('arauco2@missionary.org');
      break;
    }
  }
  return { env: e, scope: s, ss: sheet };
}

function weeklyReminderCount(e, s) {
  const subject = '[TEST] Recordatorio: Informe Semanal — ' + s.getMissionName();
  return e.state.emails.filter(
    (m) => m.subject === subject && /Arauco 2/.test(m.htmlBody || m.body || '')
  ).length;
}

// (i) SHIPPED DEFAULT — no WEEKLY_REMINDER_OWNER row touched at all.
{
  const d = makeReminderEnv(undefined);
  d.scope.runReminderAgent({ skipTimeGate: true });   // AgentReminder path
  d.scope.runWeeklyEscalation({ forceStage: 1 });     // AgentEscalation System 2
  assert.strictEqual(weeklyReminderCount(d.env, d.scope), 1,
    'with the DEFAULT config a non-submitting area must receive EXACTLY ONE weekly ' +
    'reminder, not one from each agent');
  assert.strictEqual(d.scope.getConfig('WEEKLY_REMINDER_OWNER'), 'AGENT_ESCALATION',
    'the shipped default owner must be AGENT_ESCALATION');
  console.log('overlap gate default (AGENT_ESCALATION) OK — exactly 1 reminder');
}

// (ii) The other setting must be equally single-owner.
{
  const d = makeReminderEnv('AGENT_REMINDER');
  d.scope.runReminderAgent({ skipTimeGate: true });
  d.scope.runWeeklyEscalation({ forceStage: 1 });
  assert.strictEqual(weeklyReminderCount(d.env, d.scope), 1,
    'with WEEKLY_REMINDER_OWNER=AGENT_REMINDER a non-submitting area must still receive ' +
    'EXACTLY ONE weekly reminder');
  console.log('overlap gate AGENT_REMINDER OK — exactly 1 reminder');
}

// (iii) NEGATIVE CONTROL — with the gate disabled ('BOTH'), the double-nag the
// gate exists to prevent actually happens. Proves (i)/(ii) are not vacuous.
{
  const d = makeReminderEnv('BOTH');
  d.scope.runReminderAgent({ skipTimeGate: true });
  d.scope.runWeeklyEscalation({ forceStage: 1 });
  assert.strictEqual(weeklyReminderCount(d.env, d.scope), 2,
    'WEEKLY_REMINDER_OWNER=BOTH must reproduce the duplicate-nag failure mode — ' +
    'otherwise the single-owner assertions above prove nothing');
  console.log('overlap gate negative control (BOTH) OK — 2 reminders, as designed');
}

console.log('full pipeline OK');
