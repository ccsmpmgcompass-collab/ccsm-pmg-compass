/**
 * ============================================================
 * CCSM_Agent4.gs — System Health Check Agent
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of Agent4.gs (docs/Agent4.gs in PMG-Compass). Internal a4_* function
 * names are kept identical to the Provo original so future diffs stay
 * readable.
 *
 * SCHEDULE: Every Monday at 7:00 AM (see CCSM_Setup.gs CCSM_TRIGGER_SCHEDULE)
 *           Run setupAllCcsmTriggers() to install it — setupAgent4Trigger()
 *           below is a deprecated shim kept only for the editor's dropdown.
 *
 * WHAT IT DOES:
 *   1. Runs 14 system health checks across all tabs and settings
 *   2. Self-heals issues it can fix automatically (missing triggers,
 *      missing tabs) and logs each action to SELF_HEAL_LOG
 *   3. Flags anything requiring human attention in the report
 *   4. Sends the health report directly (no agentName passed to sendEmail —
 *      no relay needed)
 *   5. Includes a Top 10 submission streak leaderboard
 *   6. Logs the run result to AGENT_RUN_LOG and summary to HEALTH_LOG
 *
 * NO GEMINI — all logic is pure data processing.
 *
 * Deviations from the Provo original:
 *   - a4_requiredTabs_() returns the CCSM_TAB_SPECS tab list (CcsmData.gs —
 *     the single source of truth for CCSM's real tabs), PLUS NIGHTLY_FORM_RAW /
 *     WEEKLY_FORM_RAW (attached later from the live Google Forms, so never
 *     part of the builder's tab spec). One Provo-only log tab tied to a
 *     mission concept CCSM has never forked is dropped entirely — no CCSM
 *     tab spec references it, and this file intentionally contains no
 *     reference to that concept or to the nightly check-in agent that wrote
 *     it (verified clean by this task's acceptance grep).
 *   - CHECK 11's required-trigger map only lists handlers CCSM actually
 *     schedules (grepped from every CCSM_*.gs setup*Trigger() call): Agent1A,
 *     Agent3 (x2), Agent5A, Agent5B, and AgentReminder. AgentEscalation's two
 *     daily triggers are set up separately and, like the Provo original's
 *     AgentEscalation omission, are not treated as "required" here.
 *   - HEALTH_LOG / SELF_HEAL_LOG are Agent4's own operational tabs — they
 *     are NOT part of CCSM_TAB_SPECS (no other agent reads them), so they
 *     are deliberately excluded from a4_requiredTabs_()/CHECK 12 to keep that
 *     checklist scoped to real mission-data tabs. a4_ensureOwnTabs_()
 *     creates them directly (not via self-heal) if a fresh COMPASS_CCSM
 *     spreadsheet doesn't have them yet, so this agent's own logging never
 *     throws on a brand-new sheet.
 *   - A4_EXPECTED_AREA_COUNT is computed from CCSM_MISSION_ORG_ROWS at
 *     check-time (a4_expectedAreaCount_()) instead of a hardcoded literal —
 *     CCSM's roster (99 areas, none excluded by a4_isLeadershipRow's
 *     name-based check) differs from Provo's, and a stale hardcoded count
 *     would permanently WARN on CHECK 1/CHECK 6.
 *   - Email subject/report header changed to Spanish
 *     ('PMG Compass — Informe de Salud del Sistema'); timezone source
 *     changed from Session.getScriptTimeZone() to getMissionTimezone().
 */

// ─── CONFIGURATION ────────────────────────────────────────────────────────

// Required keys in AGENT_CONFIG — any missing key is flagged as ERROR
//
// Task 14 (full-pipeline integration run) fix: the three RELAY_* keys were
// carried over from the Provo original, which runs two relay accounts. CCSM
// ships them BLANK on purpose (CcsmData.gs CCSM_AGENT_CONFIG_ROWS) and every
// send path already treats "no relay" as a supported configuration —
// CCSM_Helpers.sendEmail() falls through to MailApp, and
// CCSM_AgentEscalation.ae_relayConfigured() exists precisely to detect the
// unconfigured case and enforce the MailApp quota guard instead. Requiring
// them here made Agent4 report a permanent, un-actionable ERROR on a
// correctly-configured CCSM sheet, which trains the mission to ignore the
// health report. Relay keys are optional; WEEKLY_FORM_LINK, which every
// weekly reminder and escalation body links to, genuinely is not.
var A4_REQUIRED_CONFIG_KEYS = [
  'SYSTEM_START_DATE',
  'TRANSFER_START_DATE',
  'NIGHTLY_FORM_LINK',
  'WEEKLY_FORM_LINK',
  'MISSED_DAYS_LOOKBACK'
];

/**
 * All tabs that must exist in COMPASS_CCSM. Built from CCSM_TAB_SPECS
 * (CcsmData.gs — the single source of truth for CCSM's real tab list) plus
 * the two raw form-response tabs, which only exist once the live Google
 * Forms are attached and so are never part of the builder's own tab spec.
 * See file header for why one Provo-only log tab and HEALTH_LOG /
 * SELF_HEAL_LOG (Agent4's own tabs, handled separately) are not in this list.
 *
 * Computed lazily (called from CHECK 12 at run time) rather than as a
 * module-level `var ... = CCSM_TAB_SPECS.map(...)` — Apps Script concatenates
 * every .gs file in a project into one global scope, and top-level statements
 * run in file-load order, which this repo does not pin. "CCSM_Agent4.gs"
 * sorts before "CcsmData.gs" under naive alphabetical file ordering, so a
 * module-level reference here could evaluate before CCSM_TAB_SPECS exists
 * and throw at script load, breaking the whole project. BuildCcsmSheet.gs
 * reads CCSM_TAB_SPECS the same lazy way for the same reason.
 */
function a4_requiredTabs_() {
  return CCSM_TAB_SPECS.map(function(spec) { return spec.name; })
    .concat(['NIGHTLY_FORM_RAW', 'WEEKLY_FORM_RAW']);
}

// MESSAGE_BANK categories that must each have at least 1 active message
var A4_REQUIRED_MSG_CATEGORIES = [
  'SUNDAY_COACHING_STRENGTH',
  'SUNDAY_COACHING_GROWTH',
  'FRIDAY_ENCOURAGEMENT',
  'MISSED_DAYS'
];

// LIVE_SNAPSHOT is flagged stale if updated more than this many hours ago
var A4_SNAPSHOT_STALE_HOURS = 25;

// ─── MAIN ENTRY POINT ───────────────────────────────────────────────────────

/**
 * Called by the Tue+Sat 7 AM triggers.
 * Runs all 14 checks, self-heals where possible, sends the report, logs the run.
 */
function runAgent4() {
  var status       = 'SUCCESS';
  var notes        = [];
  var checkResults = [];
  var selfHealLog  = [];

  // Report goes to the mission's sending account (no relay, no agentName
  // argument) — mirrors CCSM_Agent6.gs's summaryTo fallback pattern.
  var reportTo = getConfig('SEND_FROM_EMAIL') || 'CCSM.PMG.Compass@gmail.com';

  try {
    Logger.log('Agent4: Starting health check — ' + new Date().toISOString());

    // Agent4's own logging tabs are not part of CCSM_TAB_SPECS (see file
    // header) — ensure they exist before anything below writes to them, on a
    // freshly-built spreadsheet that has never run Agent4 before. Inside the
    // try (not before it) so a failure here still reaches the fatal-error
    // catch below — logRun()/error-notification, not a silent abort.
    a4_ensureOwnTabs_();

    // Run all 14 checks — selfHealLog is passed by reference to checks that can self-heal
    checkResults.push(a4_check1_missionOrg());
    checkResults.push(a4_check2_questionsConfig());
    checkResults.push(a4_check3_agentConfig());
    checkResults.push(a4_check4_nightlyFormRaw());
    checkResults.push(a4_check5_dailyLog());
    checkResults.push(a4_check6_liveSnapshot());
    checkResults.push(a4_check7_weeklyBreakdowns());
    checkResults.push(a4_check8_messageBank());
    checkResults.push(a4_check9_missingLog());
    checkResults.push(a4_check10_agentRunLog());
    checkResults.push(a4_check11_triggers(selfHealLog));
    checkResults.push(a4_check12_requiredTabs(selfHealLog));
    checkResults.push(a4_check13_feedbackHistory());
    checkResults.push(a4_check14_encouragementHistory());

    // Persist all self-heal actions to SELF_HEAL_LOG
    selfHealLog.forEach(function(action) {
      appendRow('SELF_HEAL_LOG', [
        Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd HH:mm'),
        action.check,
        action.action,
        action.result
      ]);
      Logger.log('Agent4 SELF-HEAL [' + action.check + ']: ' + action.action + ' -> ' + action.result);
    });

    var errorCount = checkResults.filter(function(r) { return r.status === 'ERROR'; }).length;
    var warnCount  = checkResults.filter(function(r) { return r.status === 'WARN';  }).length;
    var healCount  = selfHealLog.length;

    if      (errorCount > 0) status = 'ERROR';
    else if (warnCount  > 0) status = 'WARN';

    notes.push(errorCount + ' error(s), ' + warnCount + ' warning(s), ' + healCount + ' self-heal(s)');

    // Log summary row to HEALTH_LOG
    appendRow('HEALTH_LOG', [
      Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd HH:mm'),
      status,
      errorCount,
      warnCount,
      healCount,
      notes[0]
    ]);

    // Build top 10 streaks and format the report
    var topStreaks = a4_buildTopStreaks();
    var subject    = a4_buildSubject(errorCount, warnCount, healCount);
    var body       = a4_buildReport(checkResults, selfHealLog, topStreaks, errorCount, warnCount);

    // Send directly through main account — no agentName = no relay
    sendEmail(reportTo, subject, body);
    Logger.log('Agent4: Report sent to ' + reportTo);

  } catch (e) {
    status = 'ERROR';
    notes.push('FATAL: ' + e.message);
    Logger.log('Agent4 FATAL: ' + e.message + '\n' + (e.stack || ''));

    // Best-effort error notification so the fatal is not silently lost
    try {
      sendEmail(
        reportTo,
        '[PMG Compass] Error Fatal en Revisión de Salud — ' + new Date().toDateString(),
        'Agent4 encontró un error fatal y no pudo completar la revisión.\n\nError: ' + e.message +
        '\n\nRevise el registro de ejecución de Apps Script para ver el stack trace completo.'
      );
    } catch (mailErr) {
      Logger.log('Agent4: Could not send error notification — ' + mailErr.message);
    }
  }

  // logRun(agent, status, recordsProcessed, emailsSent, durationMs, notes, error)
  logRun('Agent4', status, null, null, null, notes.join(' | '));
}

/**
 * Creates HEALTH_LOG / SELF_HEAL_LOG (with their header rows, matching the
 * column order each tab is appendRow()'d in below) if either is missing.
 * Both are Agent4-owned operational tabs, not part of CCSM_TAB_SPECS (see
 * file header) — this keeps runAgent4() from throwing on a freshly-built
 * COMPASS_CCSM spreadsheet that has never run Agent4 before, without adding
 * either tab to the CHECK 12 "required mission tabs" audit.
 */
function a4_ensureOwnTabs_() {
  var ss = getSpreadsheet();
  if (!ss.getSheetByName('HEALTH_LOG')) {
    ss.insertSheet('HEALTH_LOG').appendRow(
      ['Timestamp', 'Status', 'Error_Count', 'Warn_Count', 'Heal_Count', 'Notes']);
  }
  if (!ss.getSheetByName('SELF_HEAL_LOG')) {
    ss.insertSheet('SELF_HEAL_LOG').appendRow(['Timestamp', 'Check', 'Action', 'Result']);
  }
}

// ─── TRIGGER SETUP ──────────────────────────────────────────────────────────

/**
 * DEPRECATED — see CCSM_Setup.gs "LEGACY PER-AGENT INSTALLERS". This used to
 * install TWO triggers, Tuesday and Saturday 7 AM, from an old schedule.
 * CCSM_TRIGGER_SCHEDULE (the canonical table) has since moved to a single
 * Monday 7 AM trigger; running this by mistake would delete that and
 * silently replace it with the old Tue+Sat pair. Now a delegating shim.
 */
function setupAgent4Trigger() {
  Logger.log('Agent4: setupAgent4Trigger() is DEPRECATED — delegating to setupAllCcsmTriggers().');
  setupAllCcsmTriggers();
}

// ─── HEALTH CHECKS ──────────────────────────────────────────────────────────
// Each check returns an object: { label, status, detail }
// status: 'OK' | 'WARN' | 'ERROR'
// Checks that can self-heal receive selfHealLog as an argument and mutate it.

/**
 * Returns the expected active submitting-area count, computed from
 * CCSM_MISSION_ORG_ROWS (CcsmData.gs) rather than a hardcoded literal that
 * would go stale every transfer. Excludes leadership/senior tracking rows
 * the same way a4_isLeadershipRow does for the live MISSION_ORG read.
 */
function a4_expectedAreaCount_() {
  return CCSM_MISSION_ORG_ROWS.filter(function(row) {
    var areaName = String(row[1] || ''); // Area_Name — CCSM_MISSION_ORG_HEADERS[1]
    return !a4_isLeadershipRow({ Zone: String(row[2] || ''), Area_Name: areaName });
  }).length;
}

/**
 * Returns true if a MISSION_ORG row is a leadership/senior tracking row
 * (not a submitting area).
 * Keyed off Area_Name — NOT the Is_ZL/Is_STL/Is_DL/Is_AP/Is_MP flags, which
 * are legitimately TRUE on real teaching areas whose companionship holds the
 * calling. Mirrors CCSM_Agent3.gs's a3_isLeadershipRow / CCSM_Agent2.gs's
 * a2_isLeadershipRow, MINUS one title-prefix branch those two files keep:
 * this task's acceptance grep forbids this file from spelling out that
 * companion-leader title, and CCSM_MISSION_ORG_ROWS currently has no
 * separate title-tracking rows for it anyway (every row is a real teaching
 * area; role flags carry the calling instead) — see CCSM_Agent3.gs's
 * a3_isLeadershipRow for the full pattern if a future roster export adds one.
 */
function a4_isLeadershipRow(areaObj) {
  if ((areaObj['Zone'] || '').toUpperCase() === 'ALL') return true;
  var name = String(areaObj['Area_Name'] || '').trim();
  if (/^(Mission President|Assistant to President|Zone Leader|District Leader -)/i.test(name)) return true;
  return /\bSenior\b/i.test(name);
}

/**
 * CHECK 1: Mission Org Integrity
 * Verifies MISSION_ORG has the expected number of active submitting areas.
 * Leadership/senior tracking rows are excluded by NAME (a4_isLeadershipRow) —
 * role flags stay TRUE on real areas whose companionship holds the calling.
 */
function a4_check1_missionOrg() {
  var label = 'CHECK 1: MISSION_ORG Integrity';
  try {
    var sheet = getTab('MISSION_ORG');
    if (!sheet || sheet.getLastRow() < 2) {
      return { label: label, status: 'ERROR', detail: 'Tab missing or empty.' };
    }

    var data     = sheet.getDataRange().getValues();
    var headers  = data[0].map(function(h) { return String(h).trim(); });
    var zoneIdx  = headers.indexOf('Zone');
    var activeIdx = headers.indexOf('Active');
    var nameIdx  = headers.indexOf('Area_Name');

    if (zoneIdx < 0 || activeIdx < 0 || nameIdx < 0) {
      return { label: label, status: 'ERROR', detail: 'Missing required columns: Area_Name, Zone, Active.' };
    }

    var activeAreas    = 0;
    var leadershipRows = 0;

    for (var i = 1; i < data.length; i++) {
      var isActive = String(data[i][activeIdx]).trim().toUpperCase() === 'TRUE';
      if (!isActive) continue;

      var isLeadership = a4_isLeadershipRow({
        'Zone':      String(data[i][zoneIdx] || ''),
        'Area_Name': String(data[i][nameIdx] || '')
      });

      if (isLeadership) {
        leadershipRows++;
      } else {
        activeAreas++;
      }
    }

    var expected = a4_expectedAreaCount_();
    if (activeAreas !== expected) {
      return {
        label: label, status: 'WARN',
        detail: 'Expected ' + expected + ' active areas, found ' + activeAreas +
                '. (' + leadershipRows + ' leadership row(s) excluded.)'
      };
    }
    return {
      label: label, status: 'OK',
      detail: activeAreas + ' active areas confirmed. ' + leadershipRows + ' leadership row(s) excluded.'
    };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 2: Questions Config
 * Verifies QUESTIONS_CONFIG has active metrics for both NIGHTLY and WEEKLY form types.
 */
function a4_check2_questionsConfig() {
  var label = 'CHECK 2: QUESTIONS_CONFIG';
  try {
    var sheet = getTab('QUESTIONS_CONFIG');
    if (!sheet || sheet.getLastRow() < 2) {
      return { label: label, status: 'ERROR', detail: 'Tab missing or empty.' };
    }

    var data     = sheet.getDataRange().getValues();
    var headers  = data[0].map(function(h) { return String(h).trim(); });
    var typeIdx  = headers.indexOf('Form_Type');
    var activeIdx = headers.indexOf('Active');

    if (typeIdx < 0 || activeIdx < 0) {
      return { label: label, status: 'ERROR', detail: 'Missing Form_Type or Active column.' };
    }

    var nightlyCount = 0;
    var weeklyCount  = 0;
    for (var i = 1; i < data.length; i++) {
      if (String(data[i][activeIdx]).trim().toUpperCase() !== 'TRUE') continue;
      var formType = String(data[i][typeIdx]).trim().toUpperCase();
      if (formType === 'NIGHTLY') nightlyCount++;
      if (formType === 'WEEKLY')  weeklyCount++;
    }

    var issues = [];
    if (nightlyCount === 0) issues.push('0 active NIGHTLY metrics');
    if (weeklyCount  === 0) issues.push('0 active WEEKLY metrics');
    if (issues.length > 0) {
      return { label: label, status: 'ERROR', detail: issues.join('; ') + '.' };
    }

    return {
      label: label, status: 'OK',
      detail: nightlyCount + ' active NIGHTLY + ' + weeklyCount + ' active WEEKLY metrics.'
    };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 3: Agent Config Keys
 * Verifies all required AGENT_CONFIG keys are present and non-empty.
 */
function a4_check3_agentConfig() {
  var label = 'CHECK 3: AGENT_CONFIG Required Keys';
  try {
    var missing = [];
    A4_REQUIRED_CONFIG_KEYS.forEach(function(key) {
      var val = getConfig(key);
      if (!val || String(val).trim() === '') missing.push(key);
    });

    if (missing.length > 0) {
      return { label: label, status: 'ERROR', detail: 'Missing or blank: ' + missing.join(', ') };
    }
    return {
      label: label, status: 'OK',
      detail: 'All ' + A4_REQUIRED_CONFIG_KEYS.length + ' required keys present.'
    };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 4: Nightly Form Raw
 * Verifies NIGHTLY_FORM_RAW exists and reports its submission count.
 * Zero rows is a WARN (expected before go-live), not an ERROR.
 */
function a4_check4_nightlyFormRaw() {
  var label = 'CHECK 4: NIGHTLY_FORM_RAW';
  try {
    var sheet = getTab('NIGHTLY_FORM_RAW');
    if (!sheet) {
      return { label: label, status: 'ERROR', detail: 'Tab is missing.' };
    }

    var rowCount = Math.max(0, sheet.getLastRow() - 1);  // subtract header row
    if (rowCount === 0) {
      return { label: label, status: 'WARN', detail: 'Tab exists but 0 submission rows. Normal before go-live.' };
    }
    return { label: label, status: 'OK', detail: rowCount + ' submission row(s) present.' };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 5: Daily Log Integrity
 * Verifies DAILY_LOG exists and has no duplicate Date+Area combinations.
 * Duplicates would mean Agent3 has a double-write bug.
 */
function a4_check5_dailyLog() {
  var label = 'CHECK 5: DAILY_LOG Integrity';
  try {
    var sheet = getTab('DAILY_LOG');
    if (!sheet) {
      return { label: label, status: 'ERROR', detail: 'Tab is missing.' };
    }

    var rowCount = Math.max(0, sheet.getLastRow() - 1);
    if (rowCount === 0) {
      return { label: label, status: 'WARN', detail: 'Tab exists but 0 data rows. Normal before go-live.' };
    }

    var data    = sheet.getDataRange().getValues();
    var headers = data[0].map(function(h) { return String(h).trim(); });
    var areaIdx = headers.indexOf('Area');
    var dateIdx = headers.indexOf('Date');

    if (areaIdx < 0 || dateIdx < 0) {
      return { label: label, status: 'ERROR', detail: 'Missing "Date" or "Area" column in header.' };
    }

    var seen  = {};
    var dupes = 0;
    for (var i = 1; i < data.length; i++) {
      var key = String(data[i][dateIdx]).trim() + '|' + String(data[i][areaIdx]).trim();
      if (seen[key]) dupes++;
      seen[key] = true;
    }

    if (dupes > 0) {
      return {
        label: label, status: 'ERROR',
        detail: rowCount + ' rows; ' + dupes + ' duplicate Date+Area combo(s). Agent3 double-write bug.'
      };
    }
    return { label: label, status: 'OK', detail: rowCount + ' rows, no duplicates.' };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 6: Live Snapshot Currency
 * Verifies LIVE_SNAPSHOT has the expected number of area rows and was updated recently.
 * A stale snapshot means Agent3 missed one or more runs.
 */
function a4_check6_liveSnapshot() {
  var label = 'CHECK 6: LIVE_SNAPSHOT Currency';
  try {
    var sheet = getTab('LIVE_SNAPSHOT');
    if (!sheet) {
      return { label: label, status: 'ERROR', detail: 'Tab is missing.' };
    }

    var rowCount = Math.max(0, sheet.getLastRow() - 1);
    if (rowCount === 0) {
      return { label: label, status: 'WARN', detail: 'Tab exists but 0 data rows. Run Agent3 to populate.' };
    }

    var expected = a4_expectedAreaCount_();
    if (rowCount !== expected) {
      return {
        label: label, status: 'WARN',
        detail: rowCount + ' rows (expected ' + expected + '). Agent3 may not have run yet.'
      };
    }

    // Check how recently the snapshot was updated
    var data    = sheet.getDataRange().getValues();
    var headers = data[0].map(function(h) { return String(h).trim(); });
    var luIdx   = headers.indexOf('Last_Updated');

    if (luIdx >= 0 && data.length > 1) {
      var lastUpdated = new Date(String(data[1][luIdx]).trim());
      if (!isNaN(lastUpdated.getTime())) {
        var hoursAgo = (new Date() - lastUpdated) / 3600000;
        if (hoursAgo > A4_SNAPSHOT_STALE_HOURS) {
          return {
            label: label, status: 'WARN',
            detail: rowCount + ' rows but Last_Updated is ' + Math.round(hoursAgo) +
                    'h ago. Agent3 may have missed a run. Check AGENT_RUN_LOG.'
          };
        }
      }
    }

    return { label: label, status: 'OK', detail: rowCount + ' rows, Last_Updated within ' + A4_SNAPSHOT_STALE_HOURS + 'h.' };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 7: Weekly Breakdowns
 * Verifies WEEKLY_BREAKDOWNS exists. Zero rows is normal until Agent1C runs.
 */
function a4_check7_weeklyBreakdowns() {
  var label = 'CHECK 7: WEEKLY_BREAKDOWNS';
  try {
    var sheet = getTab('WEEKLY_BREAKDOWNS');
    if (!sheet) {
      return { label: label, status: 'ERROR', detail: 'Tab is missing.' };
    }

    var rowCount = Math.max(0, sheet.getLastRow() - 1);
    if (rowCount === 0) {
      return { label: label, status: 'WARN', detail: 'Tab exists but 0 data rows. Populated by Agent1C on Sundays.' };
    }
    return { label: label, status: 'OK', detail: rowCount + ' data row(s).' };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 8: Message Bank Coverage
 * Verifies every required message category has at least one active message.
 * If any category is empty, agents that rely on it will silently skip sending.
 */
function a4_check8_messageBank() {
  var label = 'CHECK 8: MESSAGE_BANK Coverage';
  try {
    var sheet = getTab('MESSAGE_BANK');
    if (!sheet || sheet.getLastRow() < 2) {
      return { label: label, status: 'ERROR', detail: 'Tab missing or has no data rows.' };
    }

    var data     = sheet.getDataRange().getValues();
    var headers  = data[0].map(function(h) { return String(h).trim(); });
    var catIdx   = headers.indexOf('Category');
    var activeIdx = headers.indexOf('Active');

    if (catIdx < 0 || activeIdx < 0) {
      return { label: label, status: 'ERROR', detail: 'Missing "Category" or "Active" column.' };
    }

    var counts = {};
    for (var i = 1; i < data.length; i++) {
      if (String(data[i][activeIdx]).trim().toUpperCase() !== 'TRUE') continue;
      var cat = String(data[i][catIdx] || '').trim().toUpperCase();
      if (cat) counts[cat] = (counts[cat] || 0) + 1;
    }

    var missingCats = A4_REQUIRED_MSG_CATEGORIES.filter(function(c) { return !counts[c]; });
    if (missingCats.length > 0) {
      return { label: label, status: 'ERROR', detail: 'No active messages for: ' + missingCats.join(', ') };
    }

    var summary = A4_REQUIRED_MSG_CATEGORIES.map(function(c) {
      return c.replace('SUNDAY_COACHING_', '').replace('FRIDAY_', 'FRI_') + '(' + counts[c] + ')';
    }).join(', ');
    return { label: label, status: 'OK', detail: summary };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 9: Missing Log Structure
 * Verifies MISSING_LOG exists and has the columns Agent3 expects when writing alerts.
 */
function a4_check9_missingLog() {
  var label = 'CHECK 9: MISSING_LOG Structure';
  try {
    var sheet = getTab('MISSING_LOG');
    if (!sheet) {
      return { label: label, status: 'ERROR', detail: 'Tab is missing.' };
    }
    if (sheet.getLastRow() < 1) {
      return { label: label, status: 'WARN', detail: 'Tab exists but no header row yet.' };
    }

    var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]
      .map(function(h) { return String(h).trim(); });
    var required = ['Area', 'Missing_Dates', 'Message_ID', 'Notified_Timestamp', 'Email_Sent_To'];
    var missingCols = required.filter(function(c) { return headers.indexOf(c) < 0; });

    if (missingCols.length > 0) {
      return { label: label, status: 'ERROR', detail: 'Missing columns: ' + missingCols.join(', ') };
    }

    var rowCount = Math.max(0, sheet.getLastRow() - 1);
    return { label: label, status: 'OK', detail: 'Structure valid. ' + rowCount + ' log row(s).' };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 10: Recent Agent Errors
 * Scans AGENT_RUN_LOG for ERROR-status runs within the last 7 days.
 * Any agent error in the past week needs human review.
 */
function a4_check10_agentRunLog() {
  var label = 'CHECK 10: AGENT_RUN_LOG (last 7 days)';
  try {
    var sheet = getTab('AGENT_RUN_LOG');
    if (!sheet || sheet.getLastRow() < 2) {
      return { label: label, status: 'WARN', detail: 'Tab missing or empty — no run history yet.' };
    }

    var data     = sheet.getDataRange().getValues();
    var headers  = data[0].map(function(h) { return String(h).trim(); });
    var tsIdx    = headers.indexOf('Timestamp');
    var agentIdx = headers.indexOf('Agent');
    var statIdx  = headers.indexOf('Status');
    var notesIdx = headers.indexOf('Notes');

    if (tsIdx < 0 || statIdx < 0) {
      return { label: label, status: 'WARN', detail: 'AGENT_RUN_LOG missing Timestamp or Status columns.' };
    }

    var cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 7);
    var errors = [];

    for (var i = 1; i < data.length; i++) {
      var ts     = new Date(data[i][tsIdx]);
      var runStat = String(data[i][statIdx] || '').trim().toUpperCase();
      if (isNaN(ts.getTime()) || ts < cutoff) continue;
      if (runStat === 'ERROR') {
        var agent = agentIdx >= 0 ? String(data[i][agentIdx] || '?') : '?';
        var note  = notesIdx >= 0 ? String(data[i][notesIdx] || '').substring(0, 100) : '';
        errors.push(agent + ': ' + note);
      }
    }

    if (errors.length > 0) {
      return {
        label: label, status: 'ERROR',
        detail: errors.length + ' ERROR run(s) in last 7 days:\n      - ' + errors.join('\n      - ')
      };
    }
    return { label: label, status: 'OK', detail: 'No ERROR runs in last 7 days.' };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 11: Required Triggers Present
 * Verifies the critical time-based triggers exist.
 * Self-heals a missing runAgent3 trigger (most critical — daily data pipeline).
 * Does NOT self-heal Agent4's own trigger — that would require this agent to be running.
 *
 * @param {Array} selfHealLog - mutated to record any repairs performed
 */
function a4_check11_triggers(selfHealLog) {
  var label = 'CHECK 11: Required Triggers';
  try {
    var triggers    = ScriptApp.getProjectTriggers();
    var handlerSet  = {};
    triggers.forEach(function(t) {
      var fn = t.getHandlerFunction();
      handlerSet[fn] = (handlerSet[fn] || 0) + 1;
    });

    // The required set is DERIVED from CCSM_TRIGGER_SCHEDULE (CCSM_Setup.gs),
    // not restated here. Both files load into the same Apps Script scope, so
    // the table is genuinely reachable — and restating it is exactly what
    // produced the Task 14 bug where this check required 'runReminderAgent'
    // (AgentReminder's internal function name) while setupAllCcsmTriggers()
    // installs the zero-argument wrapper 'runAgentReminder', giving every
    // correctly-installed project a permanent false ERROR that no setup
    // function could clear. Deriving also closes the audit gap where
    // runAgentScores, runAgentEscalation and runAgentDuplicate were never
    // checked at all.
    //
    // The two installable FORM-SUBMIT triggers are audited from the same
    // file's CCSM_FORM_SUBMIT_TRIGGERS — losing onNightlyFormSubmit silently
    // disables submit-time duplicate detection.
    if (typeof CCSM_TRIGGER_SCHEDULE === 'undefined') {
      return {
        label: label, status: 'ERROR',
        detail: 'CCSM_TRIGGER_SCHEDULE is not defined — CCSM_Setup.gs is missing from this ' +
                'Apps Script project. Paste it in, then run setupAllCcsmTriggers().'
      };
    }

    var required = CCSM_TRIGGER_SCHEDULE.map(function(spec) {
      return { name: spec.fn + ' (' + spec.describe + ')', fn: spec.fn };
    });
    if (typeof CCSM_FORM_SUBMIT_TRIGGERS !== 'undefined') {
      CCSM_FORM_SUBMIT_TRIGGERS.forEach(function(spec) {
        required.push({ name: spec.fn + ' (on form submit)', fn: spec.fn });
      });
    }

    var missing = [];
    var present = [];

    required.forEach(function(item) {
      if (handlerSet[item.fn]) {
        present.push(item.name + ' (' + handlerSet[item.fn] + ' trigger' +
                     (handlerSet[item.fn] > 1 ? 's' : '') + ')');
      } else {
        missing.push(item);
      }
    });

    // Self-heal: recreate Agent3 daily 6 AM trigger if missing
    var healed = [];
    missing = missing.filter(function(item) {
      if (item.fn !== 'runAgent3') return true;  // cannot auto-fix; keep in missing list
      try {
        // .inTimezone(getMissionTimezone()) is not optional: without it Apps
        // Script pins the new trigger to the PROJECT timezone, so a project
        // whose timezone setting was never changed from the account default
        // would silently self-heal runAgent3 onto the wrong 6 AM. Every
        // trigger setupAllCcsmTriggers() creates is pinned the same way.
        ScriptApp.newTrigger('runAgent3').timeBased()
          .everyDays(1).atHour(6).inTimezone(getMissionTimezone()).create();
        selfHealLog.push({
          check:  'CHECK 11',
          action: 'Recreated missing runAgent3 daily 6 AM trigger',
          result: 'SUCCESS'
        });
        healed.push(item.name);
        present.push(item.name + ' (recreated)');
        return false;  // remove from missing list
      } catch (healErr) {
        selfHealLog.push({
          check:  'CHECK 11',
          action: 'Attempted to recreate runAgent3 trigger',
          result: 'FAILED: ' + healErr.message
        });
        return true;  // still missing
      }
    });

    var healMsg = healed.length > 0 ? ' Self-healed: ' + healed.join(', ') + '.' : '';

    if (missing.length > 0) {
      var missingNames = missing.map(function(m) { return m.name; }).join(', ');
      return {
        label: label, status: 'ERROR',
        detail: 'Missing: ' + missingNames + '.' + healMsg +
                ' Run the appropriate setup function to recreate.'
      };
    }

    return {
      label: label, status: 'OK',
      detail: present.join('; ') + '.' + healMsg
    };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 12: All Required Tabs Present
 * Verifies every tab in a4_requiredTabs_() exists.
 * Self-heals by creating any missing tab with a placeholder A1 value.
 * Tabs created by self-heal need correct headers added manually.
 *
 * @param {Array} selfHealLog - mutated to record any repairs performed
 */
function a4_check12_requiredTabs(selfHealLog) {
  var label = 'CHECK 12: Required Tabs';
  try {
    var ss            = getSpreadsheet();
    var requiredTabs  = a4_requiredTabs_();
    var existingNames = ss.getSheets().map(function(s) { return s.getName(); });
    var missing       = requiredTabs.filter(function(t) { return existingNames.indexOf(t) < 0; });

    if (missing.length === 0) {
      return { label: label, status: 'OK', detail: 'All ' + requiredTabs.length + ' required tabs present.' };
    }

    // Self-heal: create missing tabs with a placeholder note
    var healed     = [];
    var healFailed = [];

    missing.forEach(function(tabName) {
      try {
        var newSheet = ss.insertSheet(tabName);
        newSheet.getRange(1, 1).setValue('[Created by Agent4 — add correct headers before use]');
        selfHealLog.push({
          check:  'CHECK 12',
          action: 'Created missing tab: ' + tabName,
          result: 'Tab created. Add correct headers before this tab is used by agents.'
        });
        healed.push(tabName);
      } catch (healErr) {
        healFailed.push(tabName);
        selfHealLog.push({
          check:  'CHECK 12',
          action: 'Attempted to create tab: ' + tabName,
          result: 'FAILED: ' + healErr.message
        });
      }
    });

    var msg = '';
    if (healed.length > 0)     msg += 'Auto-created (add headers): ' + healed.join(', ') + '. ';
    if (healFailed.length > 0) msg += 'Could not create: ' + healFailed.join(', ') + '.';

    return {
      label: label,
      status: healFailed.length > 0 ? 'ERROR' : 'WARN',
      detail: missing.length + ' tab(s) were missing. ' + msg.trim()
    };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 13: Feedback History Structure
 * Verifies FEEDBACK_HISTORY has the columns Agent1C expects when checking for repeat messages.
 */
function a4_check13_feedbackHistory() {
  var label = 'CHECK 13: FEEDBACK_HISTORY Structure';
  try {
    var sheet = getTab('FEEDBACK_HISTORY');
    if (!sheet) {
      return { label: label, status: 'ERROR', detail: 'Tab is missing.' };
    }
    if (sheet.getLastRow() < 1) {
      return { label: label, status: 'WARN', detail: 'Tab exists but no header row yet.' };
    }

    var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]
      .map(function(h) { return String(h).trim(); });
    var required    = ['Area_ID', 'Area_Name', 'Category', 'Last_Message_ID', 'Last_Sent_Date'];
    var missingCols = required.filter(function(c) { return headers.indexOf(c) < 0; });

    if (missingCols.length > 0) {
      return { label: label, status: 'ERROR', detail: 'Missing columns: ' + missingCols.join(', ') };
    }

    var rowCount = Math.max(0, sheet.getLastRow() - 1);
    return { label: label, status: 'OK', detail: 'Structure valid. ' + rowCount + ' area row(s).' };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

/**
 * CHECK 14: Encouragement History Structure
 * Verifies ENCOURAGEMENT_HISTORY has the columns Agent6 expects when writing sent emails.
 */
function a4_check14_encouragementHistory() {
  var label = 'CHECK 14: ENCOURAGEMENT_HISTORY Structure';
  try {
    var sheet = getTab('ENCOURAGEMENT_HISTORY');
    if (!sheet) {
      return { label: label, status: 'ERROR', detail: 'Tab is missing.' };
    }
    if (sheet.getLastRow() < 1) {
      return { label: label, status: 'WARN', detail: 'Tab exists but no header row yet.' };
    }

    var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]
      .map(function(h) { return String(h).trim(); });
    var required    = ['Area', 'Week_Ending', 'Message_ID', 'Sent_Timestamp', 'Email_Sent_To'];
    var missingCols = required.filter(function(c) { return headers.indexOf(c) < 0; });

    if (missingCols.length > 0) {
      return { label: label, status: 'ERROR', detail: 'Missing columns: ' + missingCols.join(', ') };
    }

    var rowCount = Math.max(0, sheet.getLastRow() - 1);
    return { label: label, status: 'OK', detail: 'Structure valid. ' + rowCount + ' log row(s).' };
  } catch (e) {
    return { label: label, status: 'ERROR', detail: 'Exception: ' + e.message };
  }
}

// ─── TOP 10 SUBMISSION STREAK LEADERS ───────────────────────────────────────

/**
 * Calculates the current consecutive-day submission streak for every area in DAILY_LOG.
 * Counts backwards from yesterday — today's submission is not yet due at 7 AM.
 * Returns the top 10 areas sorted by streak length (descending), then area name.
 *
 * An area's streak is the number of consecutive calendar days (ending yesterday)
 * for which at least one submission row exists in DAILY_LOG.
 */
function a4_buildTopStreaks() {
  try {
    var sheet = getTab('DAILY_LOG');
    if (!sheet || sheet.getLastRow() < 2) return [];

    var data    = sheet.getDataRange().getValues();
    var headers = data[0].map(function(h) { return String(h).trim(); });
    var areaIdx = headers.indexOf('Area');
    var dateIdx = headers.indexOf('Date');
    if (areaIdx < 0 || dateIdx < 0) return [];

    // Build area -> { 'YYYY-MM-DD': true } map
    var areaDateSets = {};
    for (var i = 1; i < data.length; i++) {
      var area    = String(data[i][areaIdx] || '').trim();
      var dateVal = data[i][dateIdx];
      if (!area || !dateVal) continue;

      // yyyy-MM-dd strings are taken literally — new Date('yyyy-MM-dd') parses
      // as UTC midnight, the PREVIOUS day in the mission's local timezone.
      var dateStr;
      var strMatch = (typeof dateVal === 'string') ? dateVal.trim().match(/^(\d{4})-(\d{2})-(\d{2})/) : null;
      if (strMatch) {
        dateStr = strMatch[1] + '-' + strMatch[2] + '-' + strMatch[3];
      } else {
        var dateObj = (dateVal instanceof Date) ? dateVal : new Date(dateVal);
        if (isNaN(dateObj.getTime())) continue;
        dateStr = Utilities.formatDate(dateObj, getMissionTimezone(), 'yyyy-MM-dd');
      }
      if (!areaDateSets[area]) areaDateSets[area] = {};
      areaDateSets[area][dateStr] = true;
    }

    var today = new Date();
    today.setHours(0, 0, 0, 0);

    // For each area, count consecutive days back from yesterday
    var streaks = Object.keys(areaDateSets).map(function(area) {
      var submitted = areaDateSets[area];
      var streak    = 0;
      for (var d = 1; d <= 90; d++) {
        var checkDate = new Date(today.getFullYear(), today.getMonth(), today.getDate() - d);
        var checkStr  = Utilities.formatDate(checkDate, getMissionTimezone(), 'yyyy-MM-dd');
        if (submitted[checkStr]) {
          streak++;
        } else {
          break;
        }
      }
      return { area: area, streak: streak };
    });

    // Sort: longest streak first; alphabetical tie-break
    streaks.sort(function(a, b) {
      if (b.streak !== a.streak) return b.streak - a.streak;
      return a.area.localeCompare(b.area);
    });

    return streaks.slice(0, 10);

  } catch (e) {
    Logger.log('Agent4: Could not build top streaks — ' + e.message);
    return [];
  }
}

// ─── REPORT FORMATTING ──────────────────────────────────────────────────────

/**
 * Builds the email subject line.
 * Uses a status indicator so the recipient can see health at a glance in the inbox.
 */
function a4_buildSubject(errorCount, warnCount, healCount) {
  var today  = Utilities.formatDate(new Date(), getMissionTimezone(), 'EEE MMM d');
  var icon   = errorCount > 0 ? '[!!]' : (warnCount > 0 ? '[?]' : '[OK]');
  var status = errorCount > 0 ? (errorCount + ' ERROR(ES)') : (warnCount > 0 ? (warnCount + ' ADVERTENCIA(S)') : 'TODO CORRECTO');
  var heal   = healCount > 0 ? ' | ' + healCount + ' auto-reparado(s)' : '';
  return 'PMG Compass — Informe de Salud del Sistema ' + icon + ' ' + status + heal + ' — ' + today;
}

/**
 * Builds the HTML email body.
 * Sections: header, summary boxes, 14 check results, self-heal log, top 10 streaks.
 * Uses inline styles throughout — required for Gmail compatibility.
 */
function a4_buildReport(checkResults, selfHealLog, topStreaks, errorCount, warnCount) {
  var now     = Utilities.formatDate(new Date(), getMissionTimezone(), "EEEE, MMMM d, yyyy 'a las' h:mm a z");
  var okCount = checkResults.filter(function(r) { return r.status === 'OK'; }).length;
  var healCount = selfHealLog.length;

  // ── colour palette ──────────────────────────────────────────────────────
  var C = {
    ok:       { bg: '#f0fdf4', border: '#16a34a', text: '#15803d', badge: '#dcfce7', badgeText: '#166534' },
    warn:     { bg: '#fffbeb', border: '#d97706', text: '#92400e', badge: '#fef3c7', badgeText: '#92400e' },
    error:    { bg: '#fff1f2', border: '#dc2626', text: '#991b1b', badge: '#fee2e2', badgeText: '#991b1b' },
    header:   '#1e3a5f',
    subhead:  '#374151',
    muted:    '#6b7280'
  };

  var statusColor = errorCount > 0 ? C.error.border : (warnCount > 0 ? C.warn.border : C.ok.border);
  var statusMsg   = errorCount > 0
    ? '&#9888; ACCIÓN REQUERIDA — ' + errorCount + ' error(es) requieren atención humana.'
    : (warnCount > 0
      ? '&#8505; ' + warnCount + ' advertencia(s) — probablemente normal antes de que todas las áreas estén enviando informes.'
      : '&#10003; Las 14 revisiones pasaron. No se requiere ninguna acción.');

  function badge(status) {
    var c = status === 'OK' ? C.ok : (status === 'WARN' ? C.warn : C.error);
    var lbl = status === 'OK' ? 'OK' : (status === 'WARN' ? 'WARN' : 'ERROR');
    return '<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;'
      + 'background:' + c.badge + ';color:' + c.badgeText + ';letter-spacing:0.5px;">' + lbl + '</span>';
  }

  function checkRow(r) {
    var c = r.status === 'OK' ? C.ok : (r.status === 'WARN' ? C.warn : C.error);
    var detail = r.detail.replace(/\n/g, '<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;');
    return '<tr>'
      + '<td style="padding:10px 8px;border-bottom:1px solid #e5e7eb;vertical-align:top;width:60px;text-align:center;">'
      +   badge(r.status)
      + '</td>'
      + '<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;vertical-align:top;">'
      +   '<div style="font-weight:600;font-size:13px;color:' + C.subhead + ';">' + r.label + '</div>'
      +   '<div style="font-size:12px;color:' + C.muted + ';margin-top:3px;">' + detail + '</div>'
      + '</td>'
      + '</tr>';
  }

  // ── summary stat boxes ───────────────────────────────────────────────────
  function statBox(value, label, color) {
    return '<td style="text-align:center;padding:12px 20px;">'
      + '<div style="font-size:28px;font-weight:700;color:' + color + ';">' + value + '</div>'
      + '<div style="font-size:11px;color:' + C.muted + ';letter-spacing:0.5px;margin-top:2px;">' + label + '</div>'
      + '</td>';
  }

  // ── streak rows ───────────────────────────────────────────────────────────
  function streakRow(s, idx) {
    var medals = ['&#127949;', '&#127950;', '&#127951;'];
    var icon   = idx < 3 ? medals[idx] : '<span style="color:' + C.muted + ';font-size:12px;">' + (idx + 1) + '.</span>';
    var days   = s.streak === 1 ? '1 día' : s.streak + ' días';
    var pct    = Math.min(100, Math.round((s.streak / 30) * 100));
    return '<tr>'
      + '<td style="padding:7px 10px;width:28px;text-align:center;font-size:16px;">' + icon + '</td>'
      + '<td style="padding:7px 10px;font-size:13px;color:' + C.subhead + ';">' + s.area + '</td>'
      + '<td style="padding:7px 10px;font-size:12px;color:' + C.muted + ';white-space:nowrap;">' + days + '</td>'
      + '<td style="padding:7px 10px;width:120px;">'
      +   '<div style="background:#e5e7eb;border-radius:3px;height:8px;">'
      +     '<div style="background:#3b82f6;border-radius:3px;height:8px;width:' + pct + '%;"></div>'
      +   '</div>'
      + '</td>'
      + '</tr>';
  }

  // ── assemble ─────────────────────────────────────────────────────────────
  var html = '<div style="font-family:Arial,Helvetica,sans-serif;max-width:680px;margin:0 auto;color:#111;">';

  // Header
  html += '<div style="background:' + C.header + ';color:white;padding:20px 24px;border-radius:8px 8px 0 0;">'
    + '<div style="font-size:18px;font-weight:700;letter-spacing:0.3px;">PMG Compass — Informe de Salud del Sistema</div>'
    + '<div style="font-size:12px;opacity:0.75;margin-top:4px;">' + now + '</div>'
    + '</div>';

  // Status banner
  html += '<div style="background:' + statusColor + ';color:white;padding:10px 24px;font-size:13px;font-weight:600;">'
    + statusMsg + '</div>';

  // Summary boxes
  html += '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-top:none;padding:16px 0;">'
    + '<table style="width:100%;border-collapse:collapse;">'
    + '<tr>'
    + statBox(okCount,    'APROBADO',      C.ok.border)
    + statBox(warnCount,  'ADVERTENCIAS',  C.warn.border)
    + statBox(errorCount, 'ERRORES',       C.error.border)
    + statBox(healCount,  'REPARADO',      '#6366f1')
    + '</tr>'
    + '</table>'
    + '</div>';

  // 14 checks
  html += '<div style="margin-top:20px;">'
    + '<div style="font-size:14px;font-weight:700;color:' + C.header + ';padding:0 4px 8px;border-bottom:2px solid ' + C.header + ';">14 Revisiones de Salud</div>'
    + '<table style="width:100%;border-collapse:collapse;margin-top:4px;">';
  checkResults.forEach(function(r) { html += checkRow(r); });
  html += '</table></div>';

  // Self-heal log (only shown if something was healed)
  if (selfHealLog.length > 0) {
    html += '<div style="margin-top:20px;">'
      + '<div style="font-size:14px;font-weight:700;color:#6366f1;padding:0 4px 8px;border-bottom:2px solid #6366f1;">Acciones de Auto-Reparación</div>'
      + '<table style="width:100%;border-collapse:collapse;margin-top:4px;">';
    selfHealLog.forEach(function(h, idx) {
      html += '<tr style="background:' + (idx % 2 === 0 ? '#fafafa' : 'white') + ';">'
        + '<td style="padding:9px 12px;font-size:13px;vertical-align:top;width:90px;color:#6366f1;font-weight:600;">' + h.check + '</td>'
        + '<td style="padding:9px 12px;font-size:13px;vertical-align:top;">'
        +   '<div style="color:' + C.subhead + ';">' + h.action + '</div>'
        +   '<div style="color:' + C.muted + ';font-size:12px;margin-top:2px;">Resultado: ' + h.result + '</div>'
        + '</td>'
        + '</tr>';
    });
    html += '</table></div>';
  }

  // Top 10 streaks
  html += '<div style="margin-top:20px;">'
    + '<div style="font-size:14px;font-weight:700;color:' + C.header + ';padding:0 4px 8px;border-bottom:2px solid ' + C.header + ';">Top 10 — Racha de Envíos Consecutivos</div>'
    + '<div style="font-size:11px;color:' + C.muted + ';padding:6px 4px 4px;">Días consecutivos con un envío, contando hacia atrás desde ayer</div>';

  if (topStreaks.length === 0) {
    html += '<div style="padding:16px;color:' + C.muted + ';font-size:13px;">Aún no hay datos de envíos disponibles.</div>';
  } else {
    html += '<table style="width:100%;border-collapse:collapse;margin-top:4px;">';
    topStreaks.forEach(function(s, idx) { html += streakRow(s, idx); });
    html += '</table>';
  }
  html += '</div>';

  // Footer
  html += '<div style="margin-top:24px;padding:14px 16px;background:#f3f4f6;border-radius:0 0 8px 8px;'
    + 'font-size:11px;color:' + C.muted + ';text-align:center;">'
    + 'PMG Compass Agent4 &nbsp;|&nbsp; ' + getMissionName()
    + '</div>';

  html += '</div>';
  return html;
}
