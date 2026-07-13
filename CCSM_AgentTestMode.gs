/**
 * ============================================================
 * CCSM_AgentTestMode.gs — TEST MODE Infrastructure
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of AgentTestMode.gs (docs/AgentTestMode.gs in PMG-Compass). All
 * internal names are kept identical to the Provo original — this file is a
 * mechanical, config-driven port (no mission-specific literals to translate;
 * every string here is either a tab name or an internal log message).
 *
 * All PMG Compass agents call isTestMode() before writing or sending.
 * When TEST_MODE = TRUE in AGENT_CONFIG:
 *   - All outbound emails are redirected to TEST_INBOX_EMAIL
 *   - All email subjects get '[TEST] ' prefix
 *   - All sheet writes go to tabs named TEST_[original tab name]
 *   - 'TEST MODE ACTIVE' can be logged to AUDIT_LOG on each agent run
 *
 * IMPORTANT — MIGRATION FROM CCSM_Helpers.gs:
 * isTestMode() / getTestInbox() / resolveRecipient() / resolveSubject() used
 * to live as TEMPORARY copies inside CCSM_Helpers.gs (added in Task 4 so
 * sendEmail() had something to call before this file existed). This file is
 * now the single source of truth for those four functions — the temporary
 * copies have been DELETED from CCSM_Helpers.gs. Any project pasting these
 * .gs files into Apps Script (which concatenates every file into one global
 * scope) MUST include this file, or sendEmail() will throw a
 * ReferenceError on isTestMode().
 *
 * HOW TO INTEGRATE WITH EXISTING AGENTS (already wired into CCSM_Helpers.gs):
 *   sendEmail() calls resolveRecipient()/resolveSubject() unconditionally.
 *   Any agent that writes to a tab directly (instead of through a helper)
 *   should wrap the tab name with resolveTabName().
 *
 * SETUP (run once before testing):
 *   1. Set TEST_MODE = TRUE in AGENT_CONFIG tab (CCSM_AGENT_CONFIG_ROWS
 *      already seeds this TRUE by default).
 *   2. Set TEST_INBOX_EMAIL in AGENT_CONFIG tab (defaults to
 *      CCSM.PMG.Compass@gmail.com).
 *   3. Run setupTestTabs() to create all TEST_* tabs.
 * ─────────────────────────────────────────────────────────────────────────────
 */


/**
 * Returns true if TEST_MODE is TRUE in AGENT_CONFIG.
 * Cached per execution to avoid repeated sheet reads.
 */
var _testModeCache = null;
function isTestMode() {
  if (_testModeCache !== null) return _testModeCache;
  var val = getConfig('TEST_MODE') || 'FALSE';
  _testModeCache = (String(val).trim().toUpperCase() === 'TRUE');
  return _testModeCache;
}


/**
 * Returns the test inbox email from AGENT_CONFIG.
 * Falls back to the sending account if not set.
 */
function getTestInbox() {
  var inbox = getConfig('TEST_INBOX_EMAIL') || '';
  if (!inbox) {
    Logger.log('WARNING: TEST_INBOX_EMAIL not set in AGENT_CONFIG. Falling back to SEND_FROM_EMAIL.');
    inbox = getConfig('SEND_FROM_EMAIL') || '';
  }
  return inbox;
}


/**
 * Returns the test tab name for a given production tab name.
 * e.g. 'DAILY_LOG' -> 'TEST_DAILY_LOG'
 */
function getTestTabName(tabName) {
  return 'TEST_' + tabName;
}


/**
 * Returns the real tab name to write to, based on test mode.
 * Use this anywhere an agent writes to a tab directly:
 *   var dest = resolveTabName('DAILY_LOG');
 */
function resolveTabName(tabName) {
  return isTestMode() ? getTestTabName(tabName) : tabName;
}


/**
 * Returns the real recipient for an email, based on test mode.
 * sendEmail() (CCSM_Helpers.gs) calls this unconditionally.
 */
function resolveRecipient(to) {
  return isTestMode() ? getTestInbox() : to;
}


/**
 * Returns the email subject with [TEST] prefix if in test mode.
 * sendEmail() (CCSM_Helpers.gs) calls this unconditionally.
 */
function resolveSubject(subject) {
  return isTestMode() ? '[TEST] ' + subject : subject;
}


/**
 * setupTestTabs()
 * Creates TEST_* versions of all critical CCSM tabs if they don't exist.
 * Run this once after enabling TEST_MODE = TRUE.
 */
function setupTestTabs() {
  var ss = getSpreadsheet();
  var tabsToMirror = [
    'NIGHTLY_FORM_RAW',
    'WEEKLY_FORM_RAW',
    'DAILY_LOG',
    'LIVE_SNAPSHOT',
    'WEEKLY_KI',
    'DASHBOARD_SUMMARY',
    'WEEKLY_BREAKDOWNS',
    'FEEDBACK_HISTORY',
    'SCORES',
    'AUDIT_LOG',
    'SUGGESTIONS'
  ];

  var created = [];
  var skipped = [];

  tabsToMirror.forEach(function(tabName) {
    var testName = getTestTabName(tabName);
    var existing = ss.getSheetByName(testName);
    if (existing) {
      skipped.push(testName); // already exists
      return;
    }
    var sourceSheet = ss.getSheetByName(tabName);
    if (sourceSheet && sourceSheet.getLastColumn() > 0) {
      // Copy header row only
      var headers = sourceSheet.getRange(1, 1, 1, sourceSheet.getLastColumn()).getValues();
      var newSheet = ss.insertSheet(testName);
      newSheet.getRange(1, 1, 1, headers[0].length).setValues(headers);
      created.push(testName);
    } else {
      ss.insertSheet(testName);
      created.push(testName + ' (no source — empty)');
    }
  });

  Logger.log('setupTestTabs: Created: ' + created.join(', '));
  Logger.log('setupTestTabs: Already existed: ' + skipped.join(', '));

  // Log to AUDIT_LOG
  appendRow('AUDIT_LOG', [
    Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd HH:mm:ss'),
    'AgentTestMode',
    'SETUP_TEST_TABS',
    created.length,
    '',
    'Created: ' + created.join(', ')
  ]);
}


/**
 * disableTestMode()
 * Sets TEST_MODE = FALSE in AGENT_CONFIG. Run this when ready to go live.
 */
function disableTestMode() {
  var sheet = getTab('AGENT_CONFIG');
  var data = sheet.getDataRange().getValues();
  var headers = data[0].map(function(h) { return String(h).trim(); });
  var keyIdx = headers.indexOf('Key');
  var valIdx = headers.indexOf('Value');
  if (keyIdx === -1 || valIdx === -1) {
    Logger.log('ERROR: Key or Value column not found in AGENT_CONFIG.');
    return;
  }
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][keyIdx]).trim() === 'TEST_MODE') {
      sheet.getRange(i + 1, valIdx + 1).setValue('FALSE');
      _testModeCache = false;
      Logger.log('disableTestMode: TEST_MODE set to FALSE. System is now LIVE.');
      appendRow('AUDIT_LOG', [
        Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd HH:mm:ss'),
        'AgentTestMode', 'DISABLED_TEST_MODE', 0, '', 'System set to LIVE'
      ]);
      return;
    }
  }
  Logger.log('disableTestMode: TEST_MODE key not found in AGENT_CONFIG.');
}


/**
 * enableTestMode()
 * Sets TEST_MODE = TRUE in AGENT_CONFIG.
 */
function enableTestMode() {
  var sheet = getTab('AGENT_CONFIG');
  var data = sheet.getDataRange().getValues();
  var headers = data[0].map(function(h) { return String(h).trim(); });
  var keyIdx = headers.indexOf('Key');
  var valIdx = headers.indexOf('Value');
  if (keyIdx === -1 || valIdx === -1) return;
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][keyIdx]).trim() === 'TEST_MODE') {
      sheet.getRange(i + 1, valIdx + 1).setValue('TRUE');
      _testModeCache = true;
      Logger.log('enableTestMode: TEST_MODE = TRUE. All emails/writes going to test targets.');
      return;
    }
  }
  // Key not found — append it
  sheet.appendRow(['TEST_MODE', 'TRUE']);
  _testModeCache = true;
  Logger.log('enableTestMode: TEST_MODE row added to AGENT_CONFIG.');
}


/**
 * verifyTestModeSetup()
 * Checks that TEST_MODE, TEST_INBOX_EMAIL are set and test tabs exist.
 * Run before first test to confirm everything is ready.
 */
function verifyTestModeSetup() {
  var results = [];

  var testMode = getConfig('TEST_MODE') || 'NOT SET';
  results.push('TEST_MODE: ' + testMode);

  var testInbox = getConfig('TEST_INBOX_EMAIL') || 'NOT SET';
  results.push('TEST_INBOX_EMAIL: ' + testInbox);

  var criticalTabs = ['TEST_NIGHTLY_FORM_RAW', 'TEST_DAILY_LOG', 'TEST_AUDIT_LOG'];
  var ss = getSpreadsheet();
  criticalTabs.forEach(function(t) {
    var exists = !!ss.getSheetByName(t);
    results.push(t + ': ' + (exists ? 'EXISTS' : 'MISSING — run setupTestTabs()'));
  });

  var quota = MailApp.getRemainingDailyQuota();
  results.push('Email quota remaining: ' + quota);

  Logger.log('=== TEST MODE VERIFICATION ===\n' + results.join('\n'));
  return results;
}
