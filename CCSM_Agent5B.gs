/**
 * ============================================================
 * CCSM_Agent5B.gs — Friday Encouragement Qualifier
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of Agent5B.gs (docs/Agent5B.gs in PMG-Compass) for the CCSM Spanish
 * form set. Internal a5b_* function names are kept identical to the Provo
 * original so future diffs stay readable. This agent NEVER sends email or
 * generates message text — it only decides WHICH areas qualify and hands
 * that decision to CCSM_Agent6.gs.
 *
 * SCHEDULE: Every Friday at noon
 *           Run setupAgent5BTrigger() ONCE to create the trigger.
 *
 * WHAT IT DOES:
 *   1. For each active submitting area in MISSION_ORG, checks DAILY_LOG —
 *      did they submit all 4 days Mon-Thu?
 *   2. If yes, sums their week-to-date totals and compares to GOALS_CONFIG
 *      weekly goals (falling back to GOAL_<metric_key> in AGENT_CONFIG when
 *      GOALS_CONFIG has no row for that area — see a5b_loadDefaultGoals)
 *   3. Areas where ANY metric is >= 75% of their weekly goal qualify
 *   4. Picks the single best-performing metric (highest % of goal) as the
 *      message focus
 *   5. Picks a pre-written FRIDAY_ENCOURAGEMENT MESSAGE_BANK message for
 *      that metric — no AI text is ever generated (see a5b_pickMessage)
 *   6. Saves qualifying area data to Script Properties for Agent6
 *   7. Schedules Agent6 in 1 minute
 *
 * QUALIFICATION RULES:
 *   - Must have at least one submission on EACH of Mon, Tue, Wed, Thu
 *   - At least one numeric metric must be >= 75% of its weekly goal
 *   - Best metric = highest pct-of-goal among those that qualify (>= 75%)
 *
 * CHAINS TO: Agent6 (~1 minute)
 * NO EMAIL from this agent.
 */

var A5B_ENCOURAGEMENT_THRESHOLD = 0.75;  // 75% of weekly goal qualifies

// ─── MAIN ENTRY POINT ────────────────────────────────────────────────────────

function runAgent5B() {
  var status = 'SUCCESS';
  var notes  = [];

  try {
    Logger.log('Agent5B: Starting Friday encouragement check — ' + new Date().toISOString());

    var missionOrg    = a5b_loadMissionOrg();
    var metrics       = a5b_loadActiveMetrics();
    var displayMap    = a5b_metricDisplayMap(metrics);
    var goals         = a5b_loadGoals();
    var defaultGoals  = a5b_loadDefaultGoals(metrics);
    var messageBank   = a5b_loadMessageBank();
    var lastSent      = a5b_loadLastSentMessages();

    // Determine Mon–Thu dates for the current week
    var bounds    = a5b_getWeekBounds();
    var weekStart = bounds.monday;
    var weekThru  = bounds.thursday;
    var weekEnd   = bounds.sunday;   // stored in ENCOURAGEMENT_HISTORY

    Logger.log('Agent5B: Checking week ' + weekStart + ' through ' + weekThru);

    // Load DAILY_LOG rows for Mon–Thu in one pass
    var weekData = a5b_aggregateWeekToDate(weekStart, weekThru);

    var qualifying   = [];
    var checkedCount = 0;

    missionOrg.forEach(function(areaObj) {
      var name    = areaObj['Area_Name'];
      var areaLog = weekData[name] || { submittedDates: {}, totals: {} };
      checkedCount++;

      // Must have submitted on all 4 days Mon–Thu
      var submitted4Days = a5b_submittedAllDays(areaLog.submittedDates, bounds);
      if (!submitted4Days) return;

      // Find the best qualifying metric — fall back to mission-wide defaults
      // (AGENT_CONFIG GOAL_<metric_key>) when this area has no GOALS_CONFIG row
      var areaGoals = goals[name];
      if (!areaGoals || Object.keys(areaGoals).length === 0) areaGoals = defaultGoals;
      var best = a5b_findBestMetric(areaLog.totals, areaGoals, displayMap);
      if (!best) return;  // no metric reached 75% of its goal

      // Pick an encouragement message for that metric
      var msgs    = a5b_getMessagesForMetric(messageBank, best.key, displayMap);
      var avoidId = lastSent[name] || '';
      var msgObj  = a5b_pickMessage(name, best, msgs, avoidId);
      if (!msgObj) return;

      qualifying.push({
        areaName:   name,
        zone:       areaObj['Zone']             || '',
        district:   areaObj['District']         || '',
        email1:     areaObj['Companion1_Email'] || '',
        email2:     areaObj['Companion2_Email'] || '',
        name1:      areaObj['Companion1_Name']  || '',
        name2:      areaObj['Companion2_Name']  || '',
        bestMetric: best,
        msgId:      msgObj['Message_ID'],
        msgObj:     msgObj
      });
    });

    notes.push('Checked ' + checkedCount + ' area(s) | ' + qualifying.length + ' qualify for encouragement');

    saveTempData('A5B_DATA', {
      weekEnd:    weekEnd,
      weekStart:  weekStart,
      qualifying: qualifying
    });

    scheduleNext('runAgent6', 1);
    notes.push('Agent6 scheduled in ~1 min');
    Logger.log('Agent5B: Complete — ' + notes.join(' | '));

  } catch (e) {
    status = 'ERROR';
    notes.push('ERROR: ' + e.message);
    Logger.log('Agent5B FATAL: ' + e.message + '\n' + (e.stack || ''));
  }

  // logRun(agent, status, recordsProcessed, emailsSent, durationMs, notes, error)
  logRun('Agent5B', status, null, null, null, notes.join(' | '));
}

// ─── TRIGGER SETUP ───────────────────────────────────────────────────────────

function setupAgent5BTrigger() {
  deleteTriggerByName('runAgent5B');
  ScriptApp.newTrigger('runAgent5B')
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.FRIDAY)
    .atHour(12)
    .create();
  Logger.log('Agent5B trigger created: runAgent5B every Friday at noon');
}

// ─── DATA LOADERS ─────────────────────────────────────────────────────────────

function a5b_getSheetData(tabName) {
  var sheet = getTab(tabName);
  if (!sheet || sheet.getLastRow() === 0) return [];
  return sheet.getDataRange().getValues();
}

/**
 * Loads active, non-leadership submitting areas from MISSION_ORG.
 */
function a5b_loadMissionOrg() {
  var data = a5b_getSheetData('MISSION_ORG');
  if (!data || data.length < 2) throw new Error('MISSION_ORG empty');
  var headers = data[0].map(function(h) { return String(h).trim(); });
  var rows = [];
  for (var i = 1; i < data.length; i++) {
    var obj = {};
    headers.forEach(function(h, idx) { obj[h] = String(data[i][idx] || '').trim(); });
    if (obj['Active'].toUpperCase() !== 'TRUE' || !obj['Area_Name']) continue;
    if (a5b_isLeadershipRow(obj)) continue;
    rows.push(obj);
  }
  return rows;
}

/**
 * Loads active NIGHTLY numeric metrics from QUESTIONS_CONFIG — the same
 * metric-key universe DAILY_LOG columns and GOALS_CONFIG columns use.
 * Mirrors a3_loadActiveMetrics / a5a_loadMetrics (excludes report_date,
 * exchanges, effort — only NUMBER metrics carry a weekly goal).
 */
function a5b_loadActiveMetrics() {
  var data = a5b_getSheetData('QUESTIONS_CONFIG');
  var metrics = [];
  if (!data || data.length < 2) return metrics;

  var headers = data[0].map(function(h) { return String(h).trim(); });
  for (var i = 1; i < data.length; i++) {
    var m = {};
    headers.forEach(function(h, idx) { m[h] = String(data[i][idx] || '').trim(); });
    var isActive  = m['Active'] && m['Active'].toUpperCase() === 'TRUE';
    var formType  = (m['Form_Type'] || '').toUpperCase();
    var isNightly = (formType === 'NIGHTLY' || formType === '');
    var isNumber  = (m['Data_Type'] || '').toUpperCase() === 'NUMBER';
    if (isActive && isNightly && isNumber && m['Metric_Key']) metrics.push(m);
  }
  return metrics;
}

/**
 * Returns { metric_key: display_name } for message-bank / email display text.
 */
function a5b_metricDisplayMap(metrics) {
  var map = {};
  metrics.forEach(function(m) {
    map[m['Metric_Key']] = m['Metric_Display_Name'] || m['Metric_Key'];
  });
  return map;
}

/**
 * Mission-wide default weekly goals from AGENT_CONFIG GOAL_<metric_key> rows
 * (lowercase — matching CCSM's Metric_Key convention directly; see
 * CcsmData.gs CCSM_AGENT_CONFIG_ROWS GOAL_* rows and task-2's reconciliation
 * note). Used when GOALS_CONFIG has no row for an area — without this
 * fallback an empty GOALS_CONFIG means no area can ever qualify, and Friday
 * encouragement silently never sends.
 */
function a5b_loadDefaultGoals(metrics) {
  var defaults = {};
  metrics.forEach(function(m) {
    var key = m['Metric_Key'];
    var v   = parseFloat(getConfig('GOAL_' + key));
    if (!isNaN(v) && v > 0) defaults[key] = v;
  });
  return defaults;
}

/**
 * Returns { area: { metric_key: weekly_goal } } for all metrics in
 * GOALS_CONFIG. GOALS_CONFIG is a wide table: one 'Area' column plus one
 * column per Metric_Key. Returns {} when the tab has no header/data rows
 * (its default un-populated state — see CcsmData.gs CCSM_TAB_SPECS).
 */
function a5b_loadGoals() {
  var data = a5b_getSheetData('GOALS_CONFIG');
  var goals = {};
  if (!data || data.length < 2) return goals;
  var headers = data[0].map(function(h) { return String(h).trim(); });
  var areaIdx = headers.indexOf('Area');
  if (areaIdx < 0) return goals;
  for (var i = 1; i < data.length; i++) {
    var area = String(data[i][areaIdx] || '').trim();
    if (!area) continue;
    goals[area] = {};
    headers.forEach(function(h, idx) {
      if (idx === areaIdx) return;
      var val = parseFloat(data[i][idx]);
      if (!isNaN(val) && val > 0) goals[area][h] = val;
    });
  }
  return goals;
}

/**
 * Loads active FRIDAY_ENCOURAGEMENT messages from MESSAGE_BANK.
 * Returns { metric_key_or_display: [messageObj, ...] } — also includes an
 * 'ANY' key for catch-all messages.
 */
function a5b_loadMessageBank() {
  var data = a5b_getSheetData('MESSAGE_BANK');
  var bank = {};
  if (!data || data.length < 2) return bank;
  var headers   = data[0].map(function(h) { return String(h).trim(); });
  var catIdx    = headers.indexOf('Category');
  var metricIdx = headers.indexOf('Metric');
  var activeIdx = headers.indexOf('Active');
  if (catIdx < 0 || activeIdx < 0) return bank;

  for (var i = 1; i < data.length; i++) {
    var cat    = String(data[i][catIdx]    || '').trim().toUpperCase();
    var active = String(data[i][activeIdx] || '').trim().toUpperCase();
    if (cat !== 'FRIDAY_ENCOURAGEMENT' || active !== 'TRUE') continue;
    var metric = metricIdx >= 0 ? String(data[i][metricIdx] || '').trim() : '';
    var msg    = {};
    headers.forEach(function(h, idx) { msg[h] = String(data[i][idx] || '').trim(); });
    var key = metric || 'ANY';
    if (!bank[key]) bank[key] = [];
    bank[key].push(msg);
  }
  return bank;
}

/**
 * Returns { area: last_message_id } from ENCOURAGEMENT_HISTORY.
 * Used to avoid sending the same encouragement message back-to-back.
 */
function a5b_loadLastSentMessages() {
  var data = a5b_getSheetData('ENCOURAGEMENT_HISTORY');
  var last = {};
  if (!data || data.length < 2) return last;
  var headers = data[0].map(function(h) { return String(h).trim(); });
  var areaIdx = headers.indexOf('Area');
  var msgIdx  = headers.indexOf('Message_ID');
  if (areaIdx < 0 || msgIdx < 0) return last;

  // Track most recent entry per area (last row for that area wins)
  for (var i = 1; i < data.length; i++) {
    var area = String(data[i][areaIdx] || '').trim();
    if (!area) continue;
    last[area] = String(data[i][msgIdx] || '').trim();
  }
  return last;
}

// ─── DAILY LOG AGGREGATION ────────────────────────────────────────────────────

/**
 * Reads DAILY_LOG and sums all rows for the Mon–Thu window.
 * Returns { area: { submittedDates: { 'YYYY-MM-DD': true }, totals: { metric: sum } } }
 */
function a5b_aggregateWeekToDate(weekStart, weekThru) {
  var data = a5b_getSheetData('DAILY_LOG');
  var agg  = {};
  if (!data || data.length < 2) return agg;

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var areaIdx = headers.indexOf('Area');
  var dateIdx = headers.indexOf('Date');
  if (areaIdx < 0 || dateIdx < 0) return agg;

  for (var i = 1; i < data.length; i++) {
    var dateStr = a5b_toDateString(data[i][dateIdx]);
    if (!dateStr || dateStr < weekStart || dateStr > weekThru) continue;
    var area = String(data[i][areaIdx] || '').trim();
    if (!area) continue;

    if (!agg[area]) agg[area] = { submittedDates: {}, totals: {} };
    agg[area].submittedDates[dateStr] = true;

    headers.forEach(function(h, idx) {
      if (idx < 4) return;  // skip Date/Area/Zone/District
      var val = parseFloat(data[i][idx]);
      if (isNaN(val)) return;
      agg[area].totals[h] = (agg[area].totals[h] || 0) + val;
    });
  }
  return agg;
}

// ─── QUALIFICATION LOGIC ──────────────────────────────────────────────────────

/**
 * Returns true if the area submitted on ALL four days: Mon, Tue, Wed, Thu.
 */
function a5b_submittedAllDays(submittedDates, bounds) {
  return submittedDates[bounds.monday]    &&
         submittedDates[bounds.tuesday]   &&
         submittedDates[bounds.wednesday] &&
         submittedDates[bounds.thursday];
}

/**
 * Finds the best-performing metric that is >= 75% of its weekly goal.
 * Returns { key, display, actual, goal, pct } for the highest pct, or null
 * if none qualify. Only considers metrics where goal > 0.
 * 'display' is the human-readable Spanish metric name (from QUESTIONS_CONFIG
 * Metric_Display_Name via displayMap) — used verbatim in the email template.
 */
function a5b_findBestMetric(totals, areaGoals, displayMap) {
  var best = null;
  Object.keys(areaGoals).forEach(function(metricKey) {
    var goal   = areaGoals[metricKey];
    var actual = totals[metricKey] || 0;
    if (!goal || goal <= 0) return;
    var pct = actual / goal;
    if (pct < A5B_ENCOURAGEMENT_THRESHOLD) return;
    if (!best || pct > best.pct) {
      best = {
        key:     metricKey,
        display: (displayMap && displayMap[metricKey]) || metricKey,
        actual:  actual,
        goal:    goal,
        pct:     pct
      };
    }
  });
  return best;
}

// ─── MESSAGE SELECTION ────────────────────────────────────────────────────────

/**
 * Returns messages for a specific metric key.
 * MESSAGE_BANK's Metric column may store either the raw Metric_Key
 * ('new_people_found') or its Spanish display name ('Nuevas Personas
 * Encontradas') — try the key first, then the display name, then the
 * ALL_STRONG catch-all, then the full FRIDAY_ENCOURAGEMENT pool so a
 * qualifying area never silently receives no message at all.
 */
function a5b_getMessagesForMetric(messageBank, metricKey, displayMap) {
  var specific = messageBank[metricKey] || [];
  if (specific.length > 0) return specific;

  var display = displayMap && displayMap[metricKey];
  if (display && (messageBank[display] || []).length > 0) return messageBank[display];

  if ((messageBank['ALL_STRONG'] || []).length > 0) return messageBank['ALL_STRONG'];
  if ((messageBank['ANY'] || []).length > 0) return messageBank['ANY'];

  // Last resort: any active FRIDAY_ENCOURAGEMENT message
  var all = [];
  Object.keys(messageBank).forEach(function(k) {
    messageBank[k].forEach(function(m) { all.push(m); });
  });
  return all;
}

/**
 * Picks a FRIDAY_ENCOURAGEMENT message for this area.
 * Random selection from the recency-filtered pool — all messages are curated
 * and appropriate. No Gemini call: gemini-2.5-flash's free-tier 5 RPM limit
 * would blow past Apps Script's 6-minute execution cap once more than a
 * handful of areas qualify in the same run (same reasoning as
 * CCSM_Helpers.gs pickMessage()). Always avoids avoidId (last message sent
 * to this area) when possible.
 */
function a5b_pickMessage(areaName, bestMetric, availableMessages, avoidId) {
  if (!availableMessages || availableMessages.length === 0) {
    Logger.log('Agent5B: No encouragement messages available for metric ' + bestMetric.key);
    return null;
  }

  var candidates = avoidId
    ? availableMessages.filter(function(m) { return m['Message_ID'] !== avoidId; })
    : availableMessages;
  if (candidates.length === 0) candidates = availableMessages;

  return candidates[Math.floor(Math.random() * candidates.length)];
}

// ─── DATE UTILITIES ────────────────────────────────────────────────────────────

/**
 * Returns the Mon–Sun dates for the week containing today (Friday).
 */
function a5b_getWeekBounds() {
  var today = new Date();
  today.setHours(0, 0, 0, 0);
  var day = today.getDay();  // 5 for Friday, but use actual day for safety
  var diffToMonday = (day === 0) ? -6 : 1 - day;
  var monday    = new Date(today.getFullYear(), today.getMonth(), today.getDate() + diffToMonday);
  var tuesday   = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 1);
  var wednesday = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 2);
  var thursday  = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 3);
  var sunday    = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 6);
  return {
    monday:    a5b_toDateString(monday),
    tuesday:   a5b_toDateString(tuesday),
    wednesday: a5b_toDateString(wednesday),
    thursday:  a5b_toDateString(thursday),
    sunday:    a5b_toDateString(sunday)
  };
}

function a5b_toDateString(val) {
  if (!val && val !== 0) return null;
  // yyyy-MM-dd strings must be taken literally — new Date('yyyy-MM-dd') parses
  // as UTC midnight, which is the PREVIOUS day in Santiago time.
  if (typeof val === 'string') {
    var m = val.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return m[1] + '-' + m[2] + '-' + m[3];
  }
  var d = (val instanceof Date) ? val
    : (typeof val === 'number') ? new Date(Date.UTC(1899, 11, 30) + val * 86400000)
    : new Date(String(val).trim());
  if (isNaN(d.getTime())) return null;
  return Utilities.formatDate(d, getMissionTimezone(), 'yyyy-MM-dd');
}

// Keyed off Area_Name — NOT the Is_ZL/Is_STL/Is_DL/Is_AP/Is_MP flags, which
// are legitimately TRUE on real teaching areas whose companionship holds the
// calling. Mirrors a3_isLeadershipRow / a5a_isLeadershipRow. IMOS role titles
// (Mission President, Zone Leader, District Leader, etc.) are standard
// English across all missions regardless of the mission's working language.
function a5b_isLeadershipRow(obj) {
  if ((obj['Zone'] || '').toUpperCase() === 'ALL') return true;
  var name = String(obj['Area_Name'] || '').trim();
  if (/^(Mission President|Assistant to President|Zone Leader|Sister Training Leader -|District Leader -)/i.test(name)) return true;
  return /\bSenior\b/i.test(name);
}
