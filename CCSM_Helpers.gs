/**
 * CCSM_Helpers.gs
 * ─────────────────────────────────────────────────────────────────────────────
 * Shared utility library for all CCSM (Chile Concepción South Mission) COMPASS
 * agents — a config-driven, Spanish-language fork of the original Provo
 * Helpers.gs (docs/Helpers.gs in PMG-Compass). Every function here is callable
 * from any CCSM_*.gs agent file.
 *
 * This fork removes every mission-specific literal (mission name, timezone)
 * in favor of reading them from AGENT_CONFIG via getMissionName() /
 * getMissionTimezone(), so the same file can be reused by a future mission
 * fork without hand-editing string literals scattered through the file.
 *
 * NO EXTERNAL DATABASES. Google Sheets is the only data store.
 * No Supabase. No external APIs other than Gemini.
 *
 * ═══════════════════════════════════════════════════════════════════════════
 * HARD RULE — enforced in pickMessage():
 * Gemini may ONLY select a pre-written Message_ID from MESSAGE_BANK.
 * Gemini must NEVER generate, rewrite, or modify text sent to missionaries.
 * All message text is written by humans and stored in MESSAGE_BANK.
 * (Exception: leadership coaching narratives in Agent1C are Gemini-generated
 *  and are sent to trained leaders, not missionaries.)
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * SETUP REQUIRED BEFORE ANY AGENT RUNS:
 * 1. In Apps Script → Project Settings → Script Properties, add:
 *       Key: GEMINI_API_KEY
 *       Value: your key from Google AI Studio (aistudio.google.com)
 *    The API key must NOT be stored in the spreadsheet — Script Properties only.
 * 2. Run buildCcsmSheet() (BuildCcsmSheet.gs) to create the COMPASS_CCSM
 *    spreadsheet with every tab, including a pre-filled AGENT_CONFIG.
 * 3. Attach the ES daily/weekly forms' response tabs as NIGHTLY_FORM_RAW /
 *    WEEKLY_FORM_RAW, then fill the remaining AGENT_CONFIG blanks
 *    (SYSTEM_START_DATE, form links, GEMINI key via Script Properties).
 *
 * FUNCTION INDEX:
 * ── Spreadsheet Access ─────────────────────────────────────────────────────
 *   getSpreadsheet()
 *   getTab(tabName)
 *   getTabData(tabName)
 *   getTabHeaders(tabName)
 *   appendRow(tabName, rowData)
 *   overwriteTab(tabName, dataRows)
 *
 * ── Configuration ──────────────────────────────────────────────────────────
 *   readAgentConfig()
 *   getConfig(key)
 *   getMissionName()
 *   getMissionTimezone()
 *
 * ── Email ──────────────────────────────────────────────────────────────────
 *   sendEmail(to, subject, body, agentName)
 *   testRelay()
 *
 * ── Test Mode ──────────────────────────────────────────────────────────────
 *   isTestMode() / getTestInbox() / resolveRecipient() / resolveSubject() are
 *   defined in CCSM_AgentTestMode.gs (Task 12) — sendEmail() below calls them
 *   unconditionally, so CCSM_AgentTestMode.gs must always be included
 *   alongside this file.
 *
 * ── Gemini ─────────────────────────────────────────────────────────────────
 *   callGemini(prompt)
 *   getMessageBank(category, metric)
 *   pickMessage(areaKey, category, metric, stats)
 *   checkNoRepeat(areaKey, messageId)
 *   recordMessageSent(areaKey, messageId, category)
 *
 * ── Agent Coordination ─────────────────────────────────────────────────────
 *   scheduleNext(functionName, delayMinutes)
 *   deleteTriggerByName(functionName)
 *   saveTempData(key, value)
 *   loadTempData(key)
 *   logRun(agentName, status, recordsProcessed, emailsSent, durationMs, notes, error)
 *
 * ── Scoring ─────────────────────────────────────────────────────────────────
 *   ccsmEffortScore(v)
 *
 * ── Private Helpers (underscore suffix) ───────────────────────────────────
 *   getHeaders_(tabName)
 *   col_(tabName, colName)
 */

// =============================================================================
// MODULE-LEVEL CACHES
// Both caches persist only for the duration of one script execution.
// GAS resets all global state between runs so neither can leak stale data.
//
// _configCache — holds a single read of AGENT_CONFIG (key → value map).
// _headerCache — holds one header-row read per tab (tabName → string[]).
// =============================================================================
var _configCache = null;
var _headerCache = {};

// =============================================================================
// SPREADSHEET ACCESS
// =============================================================================

/**
 * Returns the active COMPASS_CCSM Google Spreadsheet.
 */
function getSpreadsheet() {
  return SpreadsheetApp.getActiveSpreadsheet();
}

/**
 * Returns a tab (sheet) by name. Throws a clear error if the tab does not exist.
 */
function getTab(tabName) {
  var sheet = getSpreadsheet().getSheetByName(tabName);
  if (!sheet) {
    // Names the actual spreadsheet rather than a hardcoded one: this error is
    // read by whoever is on call, and it used to say "COMPASS_Main" — Utah
    // Provo's sheet, which CCSM's operators have no access to and would waste
    // real time looking for. Falls back to the CCSM name if the spreadsheet
    // handle is somehow unavailable, since this path is already an error path.
    var ssName = 'COMPASS_CCSM';
    try { ssName = getSpreadsheet().getName() || ssName; } catch (e) {}
    throw new Error(
      'Tab not found: "' + tabName + '". ' +
      'Verify the tab exists in ' + ssName + ' and matches the name in AGENT_CONFIG.'
    );
  }
  return sheet;
}

/**
 * Returns all DATA rows from a tab as a 2D array. Row 1 (header) is skipped.
 * Returns [] if the tab has no data rows.
 */
function getTabData(tabName) {
  var sheet   = getTab(tabName);
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  if (lastRow < 2 || lastCol < 1) return [];
  return sheet.getRange(2, 1, lastRow - 1, lastCol).getValues();
}

/**
 * Returns the header row (row 1) of a tab as a flat array of strings.
 */
function getTabHeaders(tabName) {
  var sheet   = getTab(tabName);
  var lastCol = sheet.getLastColumn();
  if (lastCol < 1) return [];
  return sheet.getRange(1, 1, 1, lastCol).getValues()[0].map(String);
}

/**
 * Appends a single row of data to the bottom of a tab.
 */
function appendRow(tabName, rowData) {
  getTab(tabName).appendRow(rowData);
}

/**
 * Replaces the ENTIRE tab (header included) with new rows.
 * Every caller passes [headerRow, ...dataRows], so the supplied header
 * becomes row 1. The old behavior (preserve row 1, write from row 2)
 * stacked the agent's header beneath a stale manually-created header,
 * which broke every Streamlit page reading these tabs.
 *
 * Accepts both call signatures:
 *   overwriteTab(tabName, rowsIncludingHeader)            ← preferred
 *   overwriteTab(tabName, headersIgnored, rowsIncludingHeader)  ← legacy
 */
function overwriteTab(tabName, headersOrData, optionalData) {
  var dataRows = optionalData ? optionalData : headersOrData;
  var sheet    = getTab(tabName);
  sheet.clearContents();
  if (dataRows && dataRows.length > 0) {
    sheet.getRange(1, 1, dataRows.length, dataRows[0].length).setValues(dataRows);
  }
  SpreadsheetApp.flush();
}

// =============================================================================
// CONFIGURATION
// =============================================================================

/**
 * Reads the entire AGENT_CONFIG tab and returns all settings as a plain object.
 * Result is cached for the current execution — only hits the sheet once per run.
 */
function readAgentConfig() {
  if (_configCache) return _configCache;
  var sheet = getSpreadsheet().getSheetByName('AGENT_CONFIG');
  if (!sheet) {
    throw new Error(
      'AGENT_CONFIG tab not found. ' +
      'Run buildSheetSkeleton() then populateAgentConfig() before running any agent.'
    );
  }
  var rows   = sheet.getDataRange().getValues();
  var config = {};
  for (var i = 1; i < rows.length; i++) {
    var key = String(rows[i][0]).trim();
    var val = rows[i][1];
    if (key) config[key] = val;
  }
  _configCache = config;
  return config;
}

/**
 * Returns a single config value by key, always as a string.
 * Returns null if the key does not exist in AGENT_CONFIG.
 *
 * Cast to type based on the Data_Type column in AGENT_CONFIG:
 *   NUMBER  → parseFloat(getConfig('KEY'))
 *   BOOLEAN → getConfig('KEY') === 'TRUE'
 *   DATE    → new Date(getConfig('KEY'))
 *   TEXT    → getConfig('KEY')
 */
function getConfig(key) {
  var config = readAgentConfig();
  var val    = config[key];
  return (val !== undefined && val !== '') ? String(val) : null;
}

// Lazy getters for mission identity, read from AGENT_CONFIG (MISSION_NAME /
// MISSION_TIMEZONE rows — see CcsmData.gs CCSM_AGENT_CONFIG_ROWS). Cached in
// module-level vars for the duration of one script execution; GAS resets all
// globals between runs, so this cache never leaks stale values across runs.
var _missionNameCache = null;
var _missionTimezoneCache = null;

function getMissionName() {
  if (_missionNameCache === null) {
    _missionNameCache = getConfig('MISSION_NAME') || 'PMG Compass';
  }
  return _missionNameCache;
}

function getMissionTimezone() {
  if (_missionTimezoneCache === null) {
    _missionTimezoneCache = getConfig('MISSION_TIMEZONE') || 'America/Santiago';
  }
  return _missionTimezoneCache;
}

// =============================================================================
// EMAIL
// =============================================================================

/**
 * Sends an email from PMG Compass, routing through the correct account to
 * stay within Gmail's 100 emails/day free limit.
 *
 * TEST MODE: If AgentTestMode.gs is deployed, resolveRecipient() redirects
 * all emails to TEST_INBOX_EMAIL and resolveSubject() prepends [TEST].
 * When TEST_MODE = FALSE these functions pass through unchanged.
 *
 * ROUTING (as implemented below — read the code, not this list, if they ever
 * disagree again):
 *   Agent1C          → RELAY_2_URL — Sunday coaching
 *   Agent3           → RELAY_2_URL — Missed days
 *   Agent6           → RELAY_2_URL — Friday encouragement
 *   AgentEscalation  → RELAY_2_URL — Escalation
 *   All else         → MailApp direct from the script owner's account
 *
 * Every path sets Reply-To: CCSM_REPLY_TO below.
 *
 * KNOWN GAP (final review, integration I-1): RELAY_1_URL is read by NO code
 * path — Agent1C goes to RELAY_2_URL. Configuring both relays therefore piles
 * coaching AND alerts onto one account's 100/day limit instead of splitting
 * them. Left as-is deliberately: splitting the load is a deployment decision
 * (it needs a second relay account to exist), not a code defect. Decide it
 * before TEST_MODE=FALSE at full roster scale.
 *
 * AGENT_CONFIG KEYS:
 *   RELAY_2_URL   — Web App URL of the relay script (optional; blank = direct)
 *   RELAY_SECRET  — Shared secret (must match Script Properties in the relay)
 *   RELAY_1_URL   — present but currently unread; see KNOWN GAP above
 *
 * @param {string|string[]} to        - Recipient(s).
 * @param {string}          subject   - Email subject line.
 * @param {string}          body      - HTML email body.
 * @param {string}          [agentName] - Calling agent name for routing.
 */
function sendEmail(to, subject, body, agentName) {
  // CCSM's own reply address. This was inherited verbatim from the fork and
  // pointed at the ORIGINATING mission's inbox, so every reply from a Chilean
  // missionary landed in another mission's mail. Must stay a CCSM-owned
  // address; tests/test_no_provo_residue.js enforces that.
  var REPLY_TO    = 'ccsm.pmg.compass@gmail.com';
  var SENDER_NAME = 'PMG Compass — ' + getMissionName();

  // Normalize array recipients to comma-separated string
  var rawRecipient = Array.isArray(to) ? to.join(',') : String(to);

  // ── TEST MODE HOOKS (from AgentTestMode.gs) ──────────────────────────────
  // resolveRecipient() redirects to TEST_INBOX_EMAIL when TEST_MODE = TRUE.
  // resolveSubject()   prepends [TEST] to the subject line.
  // Both functions pass through unchanged when TEST_MODE = FALSE.
  // resolveRecipient()/resolveSubject() are defined in CCSM_AgentTestMode.gs
  // (Task 12) — this file no longer carries its own temporary copies.
  var recipient    = resolveRecipient(rawRecipient);
  var finalSubject = resolveSubject(subject);
  // ─────────────────────────────────────────────────────────────────────────

  // Determine relay URL based on calling agent
  var relayUrl = null;
  if (agentName === 'Agent1C') {
    relayUrl = getConfig('RELAY_2_URL');
  } else if (agentName === 'Agent3' || agentName === 'Agent6' || agentName === 'AgentEscalation') {
    relayUrl = getConfig('RELAY_2_URL');
  } else if (agentName === 'AgentReferral') {
    relayUrl = getConfig('RELAY_3_URL');
  }

  // Attempt relay send if a URL is configured for this agent
  if (relayUrl && relayUrl.trim()) {
    var secret = (getConfig('RELAY_SECRET') || '').trim();
    if (!secret) {
      Logger.log('sendEmail WARNING: RELAY_SECRET not set. Falling back to main account.');
    } else {
      try {
        var payload = JSON.stringify({
          secret:  secret,
          to:      recipient,
          subject: finalSubject,
          body:    body,
          replyTo: REPLY_TO
        });
        var response = UrlFetchApp.fetch(relayUrl.trim(), {
          method:           'post',
          contentType:      'application/json',
          payload:          payload,
          muteHttpExceptions: true
        });
        var result = JSON.parse(response.getContentText());
        if (result.success) return; // Relay sent successfully
        Logger.log('sendEmail WARNING: relay rejected — ' + result.error + '. Falling back to main account.');
      } catch (relayErr) {
        Logger.log('sendEmail WARNING: relay call failed — ' + relayErr.message + '. Falling back to main account.');
      }
    }
  }

  // Main account send — default for non-relay agents and relay fallback
  MailApp.sendEmail({
    to:       recipient,
    subject:  finalSubject,
    htmlBody: body,
    replyTo:  REPLY_TO,
    name:     SENDER_NAME
  });
}

/**
 * Sends one test email through each relay and one directly from the main account.
 * Run ONCE after setting up the relay account to confirm routing works.
 *
 * Sends to the configured TEST_INBOX_EMAIL — never to a hardcoded address.
 * This previously mailed three live messages to the ORIGINATING mission's
 * inbox (inherited from the fork), from a zero-argument function sitting in
 * the editor's Run dropdown where a misclick reaches it.
 */
function testRelay() {
  var testTo   = (typeof getTestInbox === 'function')
    ? getTestInbox()
    : getConfig('TEST_INBOX_EMAIL');
  if (!testTo) {
    Logger.log('testRelay: TEST_INBOX_EMAIL is not set — refusing to send. Fill it in AGENT_CONFIG first.');
    return;
  }
  var testBody = '<p>CCSM PMG Compass relay test. If you received this, the relay is working correctly.</p>';
  Logger.log('testRelay: sending three test emails to ' + testTo);
  try { sendEmail(testTo, 'Relay Test — Relay 1 (Coaching)', testBody, 'Agent1C'); Logger.log('Relay 1 OK'); }
  catch (e) { Logger.log('Relay 1 FAILED — ' + e.message); }
  try { sendEmail(testTo, 'Relay Test — Relay 2 (Alerts)',   testBody, 'Agent3');  Logger.log('Relay 2 OK'); }
  catch (e) { Logger.log('Relay 2 FAILED — ' + e.message); }
  try { sendEmail(testTo, 'Relay Test — Main Account',       testBody);            Logger.log('Main OK'); }
  catch (e) { Logger.log('Main FAILED — ' + e.message); }
  Logger.log('testRelay: done. Check ' + testTo + ' for 3 emails.');
}

// =============================================================================
// GEMINI AI
//
// callGemini() is used for two purposes:
//   1. Message selection (Agent1B) — Gemini returns a short Message_ID (~15 chars)
//   2. Leadership narratives (Agent1C) — Gemini writes a coaching paragraph (~300 chars)
//
// maxOutputTokens is set to 500 to support both uses.
// =============================================================================

/**
 * Makes a Gemini API call and returns the response as a trimmed string.
 * Uses GEMINI_MODEL from AGENT_CONFIG (defaults to 'gemini-1.5-flash').
 * Uses GEMINI_API_KEY from Script Properties — never from the spreadsheet.
 *
 * @param {string} prompt - The full prompt to send to Gemini.
 * @returns {string} Gemini's text response, trimmed.
 * @throws {Error} If the API key is missing or the API returns an error.
 */
function callGemini(prompt, maxOutputTokens) {
  var apiKey = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  if (!apiKey) {
    throw new Error(
      'GEMINI_API_KEY not set. ' +
      'Go to Apps Script → Project Settings → Script Properties and add it.'
    );
  }

  // Fallback must be a model this key can actually reach: gemini-1.5-flash was
  // retired (HTTP 404) and gemini-2.0-flash has a zero quota on this key.
  var model = getConfig('GEMINI_MODEL') || 'gemini-2.5-flash';
  var url   = 'https://generativelanguage.googleapis.com/v1beta/models/' +
              model + ':generateContent?key=' + apiKey;

  var payload = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: {
      temperature:    0.4,
      maxOutputTokens: maxOutputTokens || 500
    }
  };

  var options = {
    method:             'post',
    contentType:        'application/json',
    payload:            JSON.stringify(payload),
    muteHttpExceptions: true
  };

  // Free tier: 5 RPM limit (gemini-2.5-flash) — 13-second spacing holds calls to ~4.6/min
  Utilities.sleep(13000);

  var response = UrlFetchApp.fetch(url, options);
  var code     = response.getResponseCode();
  var text     = response.getContentText();

  if (code !== 200) {
    throw new Error('Gemini API error (HTTP ' + code + '): ' + text);
  }

  var json = JSON.parse(text);
  if (json.error) {
    throw new Error('Gemini API error: ' + JSON.stringify(json.error));
  }

  return json.candidates[0].content.parts[0].text.trim();
}

/**
 * Raw MESSAGE_BANK rows, cached for the lifetime of ONE execution.
 * getMessageBank() is called up to 3x per area (strength1/strength2/growth) —
 * 60-130+ calls in a full Agent1B run — and MESSAGE_BANK is never written
 * during that run, so re-reading the sheet on every call was pure waste
 * (measured: this was the dominant cost behind Agent1B running 200+ seconds
 * and Apps Script's 6-minute execution cap being a real risk). Apps Script
 * resets every top-level var at the start of each execution, so this cache
 * can never leak stale data across runs.
 */
var _messageBankRowsCache = null;
function _messageBankRows_(tabName) {
  if (!_messageBankRowsCache) _messageBankRowsCache = getTabData(tabName);
  return _messageBankRowsCache;
}

/**
 * Reads MESSAGE_BANK and returns all ACTIVE messages for a category + metric pair.
 * Called by pickMessage() to get the candidate pool before calling Gemini.
 */
function getMessageBank(category, metric) {
  var tabName  = getConfig('MESSAGE_BANK_TAB') || 'MESSAGE_BANK';
  var rows     = _messageBankRows_(tabName);
  var C = {
    messageId:      col_(tabName, 'Message_ID'),
    category:       col_(tabName, 'Category'),
    metric:         col_(tabName, 'Metric'),
    subcategory:    col_(tabName, 'Subcategory'),
    subjectLine:    col_(tabName, 'Subject_Line'),
    bodyText:       col_(tabName, 'Body_Text'),
    pmgPage:        col_(tabName, 'PMG_Chapter'),
    pmgDescription: col_(tabName, 'PMG_Description'),
    scripture:      col_(tabName, 'Scripture'),
    scriptureText:  col_(tabName, 'Scripture_Text'),
    active:         col_(tabName, 'Active')
  };

  var messages = [];
  rows.forEach(function(row) {
    var isActive = String(row[C.active]).toUpperCase() === 'TRUE';
    if (!isActive) return;
    if (String(row[C.category]) !== category) return;
    if (String(row[C.metric])   !== metric)   return;
    messages.push({
      messageId:      String(row[C.messageId]),
      category:       String(row[C.category]),
      metric:         String(row[C.metric]),
      subcategory:    String(row[C.subcategory]),
      subjectLine:    String(row[C.subjectLine]),
      bodyText:       String(row[C.bodyText]),
      pmgPage:        String(row[C.pmgPage]),
      pmgDescription: String(row[C.pmgDescription]),
      scripture:      String(row[C.scripture]),
      scriptureText:  String(row[C.scriptureText])
    });
  });
  return messages;
}

/**
 * Raw LEADERSHIP_MESSAGE_BANK rows, cached for the lifetime of ONE execution —
 * same reasoning as _messageBankRows_ above (Agent1C picks one leadership
 * message per zone/district letter, so this is read once per run, not once
 * per letter).
 */
var _leadershipMessageBankRowsCache = null;
function _leadershipMessageBankRows_(tabName) {
  if (!_leadershipMessageBankRowsCache) _leadershipMessageBankRowsCache = getTabData(tabName);
  return _leadershipMessageBankRowsCache;
}

/**
 * Reads LEADERSHIP_MESSAGE_BANK and returns all ACTIVE leadership coaching
 * messages. Replaces the CCSM_Agent1C.gs hardcoded `_LEADERSHIP_MSGS` array
 * so mission leadership can edit the wording via the Sheet.
 *
 * PMG_Page/Scripture/Scripture_Text are returned but NOT yet verified against
 * the official Spanish edition — a1c_pickRelevantLeadershipMsg_'s caller
 * withholds them at render time until CONTENT_REVIEW.md's review is done
 * (see CCSM_DEPLOYMENT.md 8.3). Editing Theme/Subject_Line/Body_Text is safe
 * today; editing the citation columns only matters once that gate lifts.
 */
function getLeadershipMessageBank() {
  var tabName = getConfig('LEADERSHIP_MESSAGE_BANK_TAB') || 'LEADERSHIP_MESSAGE_BANK';
  var rows    = _leadershipMessageBankRows_(tabName);
  var C = {
    messageId:     col_(tabName, 'Message_ID'),
    theme:         col_(tabName, 'Theme'),
    subject:       col_(tabName, 'Subject_Line'),
    body:          col_(tabName, 'Body_Text'),
    pmgPage:       col_(tabName, 'PMG_Page'),
    scripture:     col_(tabName, 'Scripture'),
    scriptureText: col_(tabName, 'Scripture_Text'),
    active:        col_(tabName, 'Active')
  };

  var messages = [];
  rows.forEach(function(row) {
    var isActive = String(row[C.active]).toUpperCase() === 'TRUE';
    if (!isActive) return;
    messages.push({
      messageId:  String(row[C.messageId]),
      theme:      String(row[C.theme]),
      subject:    String(row[C.subject]),
      body:       String(row[C.body]),
      pmg:        String(row[C.pmgPage]),
      scripture:  String(row[C.scripture]),
      scriptText: String(row[C.scriptureText])
    });
  });
  return messages;
}

/**
 * Selects the best pre-written Message_ID for an area using Gemini.
 * Gemini's ONLY output is a Message_ID string — it does not write message text.
 */
function pickMessage(areaKey, category, metric, stats) {
  var messages = getMessageBank(category, metric);
  if (!messages || messages.length === 0) {
    Logger.log('pickMessage: No messages in MESSAGE_BANK for category=' + category + ', metric=' + metric);
    return null;
  }

  // Remove any message that was the last one sent to this area
  var eligible = messages.filter(function(msg) {
    return checkNoRepeat(areaKey, msg.messageId);
  });

  // If no-repeat filtering eliminated everything, fall back to full pool
  if (eligible.length === 0) {
    Logger.log('pickMessage: No-repeat filter left 0 options for area=' + areaKey + '. Using full pool of ' + messages.length + '.');
    eligible = messages;
  }

  // Random selection from eligible pool — all eligible messages are curated and appropriate.
  // Gemini selection was removed because gemini-2.5-flash has a 5 RPM free-tier limit:
  // 68+ areas × 2 messages each = 136 calls → exceeds both quota and Apps Script's 6-min limit.
  var idx    = Math.floor(Math.random() * eligible.length);
  var picked = eligible[idx].messageId;
  Logger.log('pickMessage: Selected ' + picked + ' for area=' + areaKey + ' (random from ' + eligible.length + ' eligible)');
  return picked;
}

/**
 * Maps areaId -> Set of Last_Message_ID values, built once per execution.
 * checkNoRepeat() is called once per CANDIDATE message inside pickMessage()
 * — several hundred times across a full Agent1B run — and this data is only
 * ever READ during that run (Agent1C's recordMessageSent(), the only writer,
 * runs in a separate later execution with its own fresh globals), so
 * building the index once and reusing it is always safe.
 */
var _noRepeatIndexCache = null;
function _noRepeatIndex_(tabName) {
  if (_noRepeatIndexCache) return _noRepeatIndexCache;
  var rows       = getTabData(tabName);
  var cAreaId    = col_(tabName, 'Area_ID');
  var cLastMsgId = col_(tabName, 'Last_Message_ID');
  var index = {};
  rows.forEach(function(row) {
    var areaId = String(row[cAreaId]);
    if (!index[areaId]) index[areaId] = {};
    index[areaId][String(row[cLastMsgId])] = true;
  });
  _noRepeatIndexCache = index;
  return _noRepeatIndexCache;
}

/**
 * Checks FEEDBACK_HISTORY to enforce the no-repeat rule.
 * Returns false (block) if this messageId is the most recently sent to this area.
 * Returns true (safe) otherwise.
 */
function checkNoRepeat(areaKey, messageId) {
  var tabName = getConfig('FEEDBACK_HISTORY_TAB') || 'FEEDBACK_HISTORY';
  var forArea = _noRepeatIndex_(tabName)[String(areaKey)];
  return !(forArea && forArea[String(messageId)]); // true = safe, false = was last sent
}

/**
 * Records a sent message in FEEDBACK_HISTORY after a successful send.
 * Shifts history: Previous ← Last, then Last = new message ID.
 *
 * @param {string} areaKey
 * @param {string} messageId
 * @param {string} category
 * @param {string} [growthMetric] - Optional. When provided and the sheet has
 *   a Last_Growth_Metric column (see CcsmData.gs CCSM_TAB_SPECS), it is set
 *   too. Used by CCSM_Agent1C.gs for SUNDAY_COACHING_GROWTH rows so next
 *   week's ranking (CCSM_Agent1A.gs a1a_rankMetrics) can avoid repeating the
 *   same growth focus two weeks running — mirrors Provo's
 *   a1c_writeFeedbackHistory behavior without duplicating its upsert logic.
 */
/**
 * areaId|category -> 0-based index into a cached copy of FEEDBACK_HISTORY's
 * data rows, built on the first recordMessageSent() call and kept in sync
 * with every write this execution makes (never re-read from the sheet).
 * a1c_recordFeedbackHistory calls this up to 2x per area — 60-90+ calls in a
 * full Agent1C run — and each used to re-read the whole tab from scratch to
 * find the one row it needed.
 */
var _feedbackHistoryCache = null;
function _feedbackHistoryCache_(tabName, numCols) {
  if (_feedbackHistoryCache) return _feedbackHistoryCache;
  var sheet   = getTab(tabName);
  var lastRow = sheet.getLastRow();
  var rows    = lastRow > 1 ? sheet.getRange(2, 1, lastRow - 1, numCols).getValues() : [];
  var cAreaId = col_(tabName, 'Area_ID');
  var cCategory = col_(tabName, 'Category');
  var index = {};
  rows.forEach(function(row, i) {
    index[String(row[cAreaId]) + '|' + String(row[cCategory])] = i;
  });
  _feedbackHistoryCache = { sheet: sheet, rows: rows, index: index };
  return _feedbackHistoryCache;
}

function recordMessageSent(areaKey, messageId, category, growthMetric) {
  var tabName = getConfig('FEEDBACK_HISTORY_TAB') || 'FEEDBACK_HISTORY';
  var now     = new Date();
  var headers = getHeaders_(tabName);
  var growthColIdx = headers.indexOf('Last_Growth_Metric'); // -1 if the sheet doesn't have it
  var C = {
    areaId:       col_(tabName, 'Area_ID'),
    areaName:     col_(tabName, 'Area_Name'),
    category:     col_(tabName, 'Category'),
    lastMsgId:    col_(tabName, 'Last_Message_ID'),
    lastSentDate: col_(tabName, 'Last_Sent_Date'),
    prevMsgId:    col_(tabName, 'Previous_Message_ID'),
    prevSentDate: col_(tabName, 'Previous_Sent_Date')
  };
  var numCols = headers.length;
  var cache   = _feedbackHistoryCache_(tabName, numCols);
  var key     = String(areaKey) + '|' + String(category);
  var rowIdx  = cache.index[key];

  if (rowIdx !== undefined) {
    var data    = cache.rows[rowIdx];
    var updated = data.slice();
    updated[C.prevMsgId]    = data[C.lastMsgId]    || '';
    updated[C.prevSentDate] = data[C.lastSentDate] || '';
    updated[C.lastMsgId]    = messageId;
    updated[C.lastSentDate] = now;
    if (growthColIdx >= 0 && growthMetric) updated[growthColIdx] = growthMetric;
    cache.sheet.getRange(rowIdx + 2, 1, 1, updated.length).setValues([updated]);
    cache.rows[rowIdx] = updated; // keep the cache in sync for any later call this execution
    return;
  }

  // New row
  var newRow = new Array(numCols).fill('');
  newRow[C.areaId]       = areaKey;
  newRow[C.areaName]     = '';
  newRow[C.category]     = category;
  newRow[C.lastMsgId]    = messageId;
  newRow[C.lastSentDate] = now;
  newRow[C.prevMsgId]    = '';
  newRow[C.prevSentDate] = '';
  if (growthColIdx >= 0 && growthMetric) newRow[growthColIdx] = growthMetric;
  cache.sheet.appendRow(newRow);
  cache.index[key] = cache.rows.length;
  cache.rows.push(newRow);
}

// =============================================================================
// AGENT COORDINATION
// =============================================================================

/**
 * Creates a one-time time-based trigger to run a function after a delay.
 * Used to chain agents: Agent1A → Agent1B → Agent1C.
 * Always deletes any existing trigger for the same function first.
 */
function scheduleNext(functionName, delayMinutes) {
  deleteTriggerByName(functionName);
  var delayMs = Math.max(delayMinutes, 1) * 60 * 1000;
  ScriptApp.newTrigger(functionName).timeBased().after(delayMs).create();
  Logger.log('scheduleNext: "' + functionName + '" scheduled in ' + delayMinutes + ' minute(s).');
}

/**
 * Deletes all project triggers for a given function name.
 */
function deleteTriggerByName(functionName) {
  var triggers = ScriptApp.getProjectTriggers();
  var count    = 0;
  triggers.forEach(function(trigger) {
    if (trigger.getHandlerFunction() === functionName) {
      ScriptApp.deleteTrigger(trigger);
      count++;
    }
  });
  if (count > 0) {
    Logger.log('deleteTriggerByName: Deleted ' + count + ' trigger(s) for "' + functionName + '".');
  }
}

/**
 * Finds/creates the Drive folder that holds chain payload files, remembering
 * its ID in Script Properties rather than looking it up by name.
 *
 * Why not DriveApp.getFoldersByName(): that method can return ANY folder in
 * the user's Drive, so Apps Script's authorization scanner assigns the
 * broad, "sensitive" https://www.googleapis.com/auth/drive scope to the
 * whole project — the one that shows Google's "app isn't verified" warning
 * on every authorization. createFolder()/getFolderById(), used only on a
 * folder this script itself created, only need the narrower drive.file
 * scope (files/folders the app created or the user opened with it), which
 * does not trigger that warning. One tiny pointer property is a cheap price
 * for staying off the sensitive-scope list.
 */
function ccsmTempDataFolder_() {
  var FOLDER_NAME  = 'CCSM Chain Data (auto-generated — safe to empty)';
  var props        = PropertiesService.getScriptProperties();
  var folderIdProp = 'CCSM_TEMP_FOLDER_ID';
  var existingId    = props.getProperty(folderIdProp);

  if (existingId) {
    try { return DriveApp.getFolderById(existingId); } catch (e) {} // trashed/deleted -- recreate below
  }

  var folder = DriveApp.createFolder(FOLDER_NAME);
  props.setProperty(folderIdProp, folder.getId());
  return folder;
}

/**
 * Serializes a value to JSON and stores it in a Drive file, used to pass data
 * between chained agents (Agent1A -> Agent1B -> Agent1C). Script Properties
 * only ever holds a tiny pointer (the Drive file ID) — never the payload
 * itself.
 *
 * Why not Script Properties directly (the old approach): that store caps its
 * WHOLE project-wide total at 500KB, shared with every other feature that
 * uses it (escalation dedup keys, config caches, ...). The Sunday chain
 * payloads (A1A_DATA / A1B_DATA: 68 areas of stats + full message texts +
 * KI/trend/metas roll-ups) run past 900KB combined — already at 188% of that
 * budget on their own before anything else touches it. That is a hard,
 * structural ceiling, not a tuning problem: chunking across more property
 * keys (the old scheme) doesn't help, because the 500KB cap is on the total
 * store, not any one key. It was the proven cause of Agent1C never
 * completing a single run (AGENT_RUN_LOG: 1A x3, 1B x2, 1C x0) — see
 * [[ccsm-coaching-email]]. Drive has no comparable ceiling for a project's
 * own files.
 */
function saveTempData(key, value) {
  var json  = JSON.stringify(value);
  var props = PropertiesService.getScriptProperties();

  ccsmDeleteTempDataFile_(key, props);

  var file = ccsmTempDataFolder_().createFile(key + '.json', json, MimeType.PLAIN_TEXT);
  props.setProperty(key + '__driveId', file.getId());
  Logger.log('saveTempData: Saved "' + key + '" to Drive file ' + file.getId() +
             ' (' + json.length + ' chars).');
}

/**
 * Loads and deserializes a value previously saved with saveTempData().
 * Returns null if the key was never saved, was already cleared, or its
 * Drive file has gone missing.
 */
function loadTempData(key) {
  var props = PropertiesService.getScriptProperties();
  var id    = props.getProperty(key + '__driveId');
  if (!id) {
    Logger.log('loadTempData: No data found for key "' + key + '".');
    return null;
  }
  try {
    var json = DriveApp.getFileById(id).getBlob().getDataAsString();
    return JSON.parse(json);
  } catch (e) {
    Logger.log('loadTempData: Drive file for key "' + key + '" (id ' + id + ') unreadable: ' + e.message);
    return null;
  }
}

/**
 * Deletes a chain payload's Drive file and its Script Properties pointer.
 * Agent1C calls this at the end of the chain, once every recipient has their
 * email, so nothing lingers in Drive between Mondays.
 */
function clearTempData(key) {
  ccsmDeleteTempDataFile_(key, PropertiesService.getScriptProperties());
}

/**
 * Shared cleanup: trashes the Drive file behind `key` (if any) and its
 * pointer property. Also deletes any leftover key/key__N/key__chunks
 * properties from the pre-Drive chunking scheme, so a store that still has
 * an old stuck payload resident self-heals the first time either agent in
 * the chain touches that key again.
 */
function ccsmDeleteTempDataFile_(key, props) {
  var id = props.getProperty(key + '__driveId');
  if (id) {
    try { DriveApp.getFileById(id).setTrashed(true); } catch (e) {}
    props.deleteProperty(key + '__driveId');
  }
  var oldChunks = parseInt(props.getProperty(key + '__chunks') || '0', 10);
  for (var c = 0; c < oldChunks; c++) props.deleteProperty(key + '__' + c);
  props.deleteProperty(key + '__chunks');
  props.deleteProperty(key);
}

/**
 * Appends a structured row to AGENT_RUN_LOG recording the result of an agent run.
 * Every agent calls this at the very end — success, partial, or failure.
 * Written defensively: a failed log write never crashes the calling agent.
 */
function logRun(agentName, status, recordsProcessed, emailsSent, durationMs, notes, error) {
  var row = [
    new Date(),
    agentName            || 'Unknown',
    status               || 'UNKNOWN',
    Math.round((durationMs || 0) / 1000),
    recordsProcessed != null ? recordsProcessed : 0,
    emailsSent       != null ? emailsSent       : 0,
    error  || '',
    notes  || ''
  ];
  try {
    appendRow('AGENT_RUN_LOG', row);
  } catch (e) {
    Logger.log('logRun() could not write to AGENT_RUN_LOG: ' + e.message + ' | Entry: ' + JSON.stringify(row));
  }
}

// =============================================================================
// SCORING
// =============================================================================

/**
 * Converts a nightly effort-question answer (CCSM_NIGHTLY_QUESTIONS 'effort',
 * CCSM_FORM_STRUCTURAL.effortChoices in CcsmData.gs) into a numeric score.
 * 'Todo' = 3, 'La mayor parte' = 2, 'Algo' = 1. Any other value (blank,
 * unrecognized) scores 0 rather than throwing, since callers (Agent2/
 * AgentScores and friends) aggregate this across many rows and a single bad
 * cell should not abort the whole run.
 */
function ccsmEffortScore(v) {
  var SCORES = { 'Todo': 3, 'La mayor parte': 2, 'Algo': 1 };
  return Object.prototype.hasOwnProperty.call(SCORES, v) ? SCORES[v] : 0;
}

// =============================================================================
// PRIVATE HELPERS
// =============================================================================

/**
 * Returns the cached header array for a tab; reads from sheet only on first call.
 */
function getHeaders_(tabName) {
  if (!_headerCache[tabName]) {
    _headerCache[tabName] = getTabHeaders(tabName);
  }
  return _headerCache[tabName];
}

/**
 * Returns the 0-based column index for a named column in a tab.
 * Throws a clear error if the column is not found.
 *
 * Usage:
 *   var cAreaId = col_('FEEDBACK_HISTORY', 'Area_ID');
 *   var value   = row[cAreaId];
 *
 * For getRange() (1-based): col_('TAB', 'Col') + 1
 */
function col_(tabName, colName) {
  var headers = getHeaders_(tabName);
  var idx     = headers.indexOf(colName);
  if (idx === -1) {
    throw new Error(
      'Column "' + colName + '" not found in tab "' + tabName + '". ' +
      'Expected headers: [' + headers.join(', ') + ']. ' +
      'Verify buildSheetSkeleton() was run and the column name matches exactly.'
    );
  }
  return idx;
}

/**
 * Checks Gemini API quota status by making a minimal test call.
 * Run this function directly in Apps Script to see your quota state.
 *
 * Reads the retry delay from 429 responses to diagnose which limit was hit:
 *   < 120 seconds  → per-minute rate limit (15 RPM) — resets shortly
 *   > 3600 seconds → daily limit (1,500 RPD) — resets at midnight UTC
 *   200 OK         → quota is available, shows response to confirm model works
 */
function checkGeminiQuota() {
  var apiKey = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  if (!apiKey) { Logger.log('ERROR: GEMINI_API_KEY not set in Script Properties.'); return; }

  var model = getConfig('GEMINI_MODEL') || 'gemini-2.5-flash';
  var url   = 'https://generativelanguage.googleapis.com/v1beta/models/' +
              model + ':generateContent?key=' + apiKey;

  var payload = {
    contents: [{ parts: [{ text: 'Reply with the single word: OK' }] }],
    generationConfig: { maxOutputTokens: 5, temperature: 0 }
  };

  var response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  var code = response.getResponseCode();
  var text = response.getContentText();

  if (code === 200) {
    var json   = JSON.parse(text);
    var answer = json.candidates[0].content.parts[0].text.trim();
    Logger.log('✅ QUOTA OK — Model: ' + model + ' | Response: "' + answer + '" | Quota is available.');
    return;
  }

  if (code === 429) {
    var retryMatch = text.match(/retry.*?(\d+(\.\d+)?)s/i);
    var retrySec   = retryMatch ? parseFloat(retryMatch[1]) : null;

    Logger.log('❌ 429 QUOTA EXCEEDED — Model: ' + model);

    if (retrySec !== null) {
      if (retrySec < 120) {
        Logger.log('   ⏱ Retry in: ' + Math.ceil(retrySec) + 's → PER-MINUTE limit hit (5 RPM on gemini-2.5-flash). Resets in under 2 minutes.');
      } else {
        var hrs  = Math.floor(retrySec / 3600);
        var mins = Math.floor((retrySec % 3600) / 60);
        Logger.log('   ⏱ Retry in: ' + hrs + 'h ' + mins + 'm → DAILY limit hit (1,500 RPD). Resets at midnight UTC.');
      }
    } else {
      Logger.log('   Could not parse retry delay. Raw response: ' + text.substring(0, 500));
    }
    return;
  }

  Logger.log('⚠️ Unexpected response — HTTP ' + code + ': ' + text.substring(0, 500));
}

/**
 * Lists all Gemini models available to this API key and whether they support generateContent.
 * Run this from the Apps Script editor to find valid model names.
 */
function listGeminiModels() {
  var apiKey = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  if (!apiKey) { Logger.log('ERROR: GEMINI_API_KEY not set in Script Properties.'); return; }

  var url = 'https://generativelanguage.googleapis.com/v1beta/models?key=' + apiKey;
  var response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  var code = response.getResponseCode();
  var text = response.getContentText();

  if (code !== 200) {
    Logger.log('ERROR listing models — HTTP ' + code + ': ' + text.substring(0, 500));
    return;
  }

  var json   = JSON.parse(text);
  var models = json.models || [];
  Logger.log('Available models (' + models.length + ' total):');
  models.forEach(function(m) {
    var supportsGenerate = (m.supportedGenerationMethods || []).indexOf('generateContent') !== -1;
    if (supportsGenerate) {
      Logger.log('  ✅ ' + m.name + ' — ' + (m.displayName || '') + ' | inputTokenLimit: ' + (m.inputTokenLimit || '?'));
    }
  });
  Logger.log('(Models without generateContent support omitted)');
}
