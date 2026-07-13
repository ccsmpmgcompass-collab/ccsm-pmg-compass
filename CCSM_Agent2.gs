/**
 * ============================================================
 * CCSM_Agent2.gs — Transfer Goal Recalibration
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of Agent2.gs (docs/Agent2.gs in PMG-Compass). Internal a2_* function
 * names are kept identical to the Provo original so future diffs stay
 * readable.
 *
 * WHEN TO RUN: Once per transfer (every 6 weeks), manually or via one-time trigger.
 *              Run setupAgent2OnceTrigger() to fire it in ~2 minutes.
 *
 * WHAT IT DOES:
 *   1. Reads up to 3 transfers of DAILY_LOG history (current + 2 prior)
 *   2. Per area per nightly metric: computes weekly averages per transfer period
 *   3. Determines trend: Beating Goal | Improving | Declining | Inconsistent
 *   4. Suggests a new weekly goal:
 *        Beating Goal  → avg × 1.05, capped at current_goal × 1.5
 *        Below Goal    → avg × 1.10, capped at current_goal × 1.5
 *   5. Writes full per-area per-metric analysis to GOAL_RECALIBRATION tab
 *   6. Logs to AGENT_RUN_LOG
 *
 * No email is sent — leadership reviews and applies suggestions directly in
 * the PMG Compass Goals → Goal Recalibration tab, per area, per metric.
 *
 * REQUIRED AGENT_CONFIG KEYS:
 *   TRANSFER_START_DATE     — YYYY-MM-DD start of current transfer
 *   GOAL_{metric_key}       — current weekly goal per metric (e.g. GOAL_new_people_found = 5)
 *
 * GOAL_RECALIBRATION COLUMNS (written by this agent, self-initialized —
 * CcsmData.gs's CCSM_TAB_SPECS lists this tab with headers: null):
 *   Analysis_Date | Area | Zone | District | Metric_Key | Metric_Display_Name |
 *   Current_Goal | Avg_Week_T1 | Avg_Week_T2 | Avg_Week_T3 | Trend | Suggested_Goal
 *
 * Deviation — goal-key casing (carried forward from the Task 2 review):
 * the Provo original reads getConfig('GOAL_' + key.toUpperCase()), but
 * CCSM_AGENT_CONFIG_ROWS (CcsmData.gs) seeds GOAL_<metric_key> rows in
 * LOWERCASE, matching Metric_Key's real casing (e.g. GOAL_new_people_found,
 * not GOAL_NEW_PEOPLE_FOUND). a2_loadAreaGoals() below reads
 * getConfig('GOAL_' + key) with no case transform — the uppercase lookup
 * would never match anything seeded here and would silently return 0 for
 * every metric, exactly the bug this fork corrects. TRANSFER_SCHEDULE's real
 * header names (Transfer_Number | Start_Date | Weeks | Status, CcsmData.gs
 * CCSM_TAB_SPECS) already match what a2_loadRealTransferHistory_() reads
 * ('Start_Date' / 'Status'), so no change was needed there.
 */

var A2_TRANSFER_DAYS = 42;   // 6 weeks per transfer

// ─── MAIN ENTRY POINT ─────────────────────────────────────────────────────

function runAgent2() {
  var startTime = new Date();
  var status    = 'SUCCESS';
  var notes     = [];

  try {
    Logger.log('Agent2: Starting goal recalibration — ' + startTime.toISOString());

    // ── 1. Load reference data ─────────────────────────────────────────────────
    var missionOrg = a2_loadMissionOrg();
    var metrics    = a2_loadNightlyMetrics();
    var transfers  = a2_loadTransferBoundaries();
    var goals      = a2_loadAreaGoals(metrics);

    Logger.log('Agent2: ' + metrics.length + ' metrics | ' + transfers.length + ' transfer(s) of history');

    // ── 2. Load and analyze DAILY_LOG ──────────────────────────────────────────
    var logData      = a2_loadDailyLog(transfers, metrics);
    var analysisRows = a2_analyzeAllAreas(missionOrg, logData, metrics, goals, transfers);

    notes.push('Areas analyzed: ' + Object.keys(logData).length);

    // ── 3. Write GOAL_RECALIBRATION tab ────────────────────────────────────────
    var rowsWritten = a2_writeGoalRecalibration(analysisRows, metrics, transfers);
    notes.push('GOAL_RECALIBRATION: ' + rowsWritten + ' rows written');

    Logger.log('Agent2: Complete — ' + notes.join(' | '));

  } catch (e) {
    status = 'ERROR';
    notes.push('ERROR: ' + e.message);
    Logger.log('Agent2 FATAL: ' + e.message + '\n' + (e.stack || ''));
  }

  // logRun(agent, status, recordsProcessed, emailsSent, durationMs, notes, error)
  logRun('Agent2', status, null, null, null, notes.join(' | '));
}

// ─── TRIGGER SETUP ────────────────────────────────────────────────────────────

/**
 * Creates a one-time trigger to fire runAgent2 in ~2 minutes.
 * Use this instead of running directly when you want a logged, triggered run.
 * Safe to call again — deletes any existing Agent2 trigger first.
 */
function setupAgent2OnceTrigger() {
  deleteTriggerByName('runAgent2');
  ScriptApp.newTrigger('runAgent2').timeBased().after(2 * 60 * 1000).create();
  Logger.log('Agent2: trigger set — will fire in ~2 minutes.');
}

// ─── DATA LOADERS ─────────────────────────────────────────────────────────────

/**
 * Loads all active MISSION_ORG rows as objects keyed by column header.
 */
function a2_loadMissionOrg() {
  var sheet = getTab('MISSION_ORG');
  var data  = sheet.getDataRange().getValues();
  if (!data || data.length < 2) throw new Error('MISSION_ORG is empty');

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var areas   = [];

  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    var obj = {};
    headers.forEach(function(h, idx) {
      obj[h] = (row[idx] != null) ? String(row[idx]).trim() : '';
    });
    if (obj['Active'] && obj['Active'].toUpperCase() === 'TRUE' && obj['Area_Name']) {
      areas.push(obj);
    }
  }
  return areas;
}

/**
 * Loads active NIGHTLY metrics from QUESTIONS_CONFIG.
 * Weekly metrics (ki_*, leader_call, correlation_meeting, etc.) are excluded —
 * they are not in DAILY_LOG.
 */
function a2_loadNightlyMetrics() {
  var data = getTabData('QUESTIONS_CONFIG');
  if (!data || data.length === 0) throw new Error('QUESTIONS_CONFIG has no data rows');

  var headers = getTabHeaders('QUESTIONS_CONFIG').map(function(h) { return String(h).trim(); });
  var metrics = [];

  data.forEach(function(row) {
    var m = {};
    headers.forEach(function(h, idx) { m[h] = String(row[idx] || '').trim(); });

    var isActive  = m['Active'].toUpperCase() === 'TRUE';
    var formType  = m['Form_Type'].toUpperCase();
    var isNightly = formType === 'NIGHTLY';

    if (isActive && isNightly && m['Metric_Key']) metrics.push(m);
  });

  return metrics;
}

/**
 * Computes date boundaries for up to 3 transfers of history.
 * T1 = current transfer (may be partial), T2 = previous, T3 = two transfers ago.
 * Returns array of {label, start, end, weeks} objects.
 *
 * T2/T3 boundaries come from TRANSFER_SCHEDULE's real Actual rows when
 * available (see a2_loadRealTransferHistory_) — not every transfer is
 * exactly 6 weeks, so a fixed-42-days-back guess silently drifted from the
 * mission's real historical transfer dates for 5- or 7-week transfers. Falls
 * back to the old 42-day guess for whichever period(s) TRANSFER_SCHEDULE
 * doesn't have real history for yet (e.g. immediately after this feature is
 * added, before 2 more real transfers have been logged).
 */
function a2_loadTransferBoundaries() {
  var rawStart = getConfig('TRANSFER_START_DATE');
  if (!rawStart) throw new Error('TRANSFER_START_DATE not set in AGENT_CONFIG');

  // TRANSFER_START_DATE may arrive as a stringified Date object ("Mon Jun 30
  // 2026 ...") because AGENT_CONFIG date-formatted cells return Date objects
  // from getValues(), and getConfig() just calls String() on whatever it
  // reads. Splitting that raw string on dashes produced an Invalid Date,
  // which made every downstream avgT1 (this transfer's weekly average)
  // silently become NaN/0 for every area and metric. a2_toDateString already
  // normalizes Date/serial/string inputs correctly (same pattern as
  // a3_toDateString in CCSM_Agent3.gs) and a2_parseDate already expects a
  // real "YYYY-MM-DD" string.
  var startStr = a2_toDateString(rawStart);
  if (!startStr) throw new Error('TRANSFER_START_DATE is not a valid date: "' + rawStart + '"');

  var t1Start = a2_parseDate(startStr);
  var today   = new Date(); today.setHours(12, 0, 0, 0);

  var t1Weeks = Math.max(1, Math.ceil((today - t1Start) / (7 * 86400000)));

  var real = a2_loadRealTransferHistory_(t1Start);  // up to 2 real periods, most recent first

  var t2;
  if (real.length >= 1) {
    t2 = real[0];
  } else {
    var t2End   = new Date(t1Start); t2End.setDate(t2End.getDate() - 1);
    var t2Start = new Date(t1Start); t2Start.setDate(t2Start.getDate() - A2_TRANSFER_DAYS);
    t2 = { start: t2Start, end: t2End, weeks: 6 };
  }

  var t3;
  if (real.length >= 2) {
    t3 = real[1];
  } else {
    var t3End   = new Date(t2.start); t3End.setDate(t3End.getDate() - 1);
    var t3Start = new Date(t2.start); t3Start.setDate(t3Start.getDate() - A2_TRANSFER_DAYS);
    t3 = { start: t3Start, end: t3End, weeks: 6 };
  }

  return [
    { label: 'Current',   start: t1Start,  end: today,   weeks: t1Weeks },
    { label: 'Previous',  start: t2.start, end: t2.end,  weeks: t2.weeks },
    { label: '2 Ago',     start: t3.start, end: t3.end,  weeks: t3.weeks }
  ];
}

/**
 * Reads TRANSFER_SCHEDULE and returns up to 2 real Actual-row periods
 * strictly before t1Start, most-recent-first: [{start, end, weeks}, ...].
 * Returns [] if the tab doesn't exist, has no data, or has no Actual rows
 * before the current transfer — a2_loadTransferBoundaries() falls back to
 * the fixed 42-day guess in that case, so a missing/not-yet-populated
 * schedule never breaks goal recalibration.
 *
 * TRANSFER_SCHEDULE's real CCSM header order is Transfer_Number | Start_Date
 * | Weeks | Status (CcsmData.gs CCSM_TAB_SPECS) — this reads 'Start_Date' and
 * 'Status' by name, so it already matches without changes.
 */
function a2_loadRealTransferHistory_(t1Start) {
  var sheet = getSpreadsheet().getSheetByName('TRANSFER_SCHEDULE');
  if (!sheet || sheet.getLastRow() < 2) return [];

  var data    = sheet.getDataRange().getValues();
  var headers = data[0];
  var startIdx  = headers.indexOf('Start_Date');
  var statusIdx = headers.indexOf('Status');
  if (startIdx < 0 || statusIdx < 0) return [];

  var actualStarts = [];
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][statusIdx]).trim() !== 'Actual') continue;
    var d = data[i][startIdx];
    if (!(d instanceof Date)) continue;
    var norm = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 12);
    if (norm < t1Start) actualStarts.push(norm);
  }
  actualStarts.sort(function(a, b) { return b - a; });  // most recent first

  var periods         = [];
  var prevEndBoundary = t1Start;  // each period ends the day before the next one starts
  for (var j = 0; j < actualStarts.length && j < 2; j++) {
    var start = actualStarts[j];
    var end   = new Date(prevEndBoundary); end.setDate(end.getDate() - 1);
    var weeks = Math.max(1, (prevEndBoundary - start) / (7 * 86400000));
    periods.push({ start: start, end: end, weeks: weeks });
    prevEndBoundary = start;
  }
  return periods;
}

/**
 * Loads each area's own goal per metric, falling back to the mission-wide
 * AGENT_CONFIG default when an area has no GOALS_CONFIG override. Bulk-reads
 * GOALS_CONFIG once (mirrors a2_loadDailyLog's read-once-then-index pattern)
 * rather than one sheet read per area.
 *
 * CASING FIX (carried forward from the Task 2 review — see file header):
 * the mission-default lookup reads getConfig('GOAL_' + key) with NO case
 * transform, matching CCSM_AGENT_CONFIG_ROWS' real seeded casing
 * (GOAL_new_people_found, not GOAL_NEW_PEOPLE_FOUND — the Provo original's
 * .toUpperCase() would never match anything seeded here and silently return
 * 0 for every metric).
 *
 * Returns { missionDefaults: {metricKey: value}, forArea: function(areaName, metricKey) }
 */
function a2_loadAreaGoals(metrics) {
  var missionDefaults = {};
  metrics.forEach(function(m) {
    var key = m['Metric_Key'];
    var val = getConfig('GOAL_' + key);
    missionDefaults[key] = val ? (parseFloat(val) || 0) : 0;
  });

  var byArea = {};
  try {
    var headers = getTabHeaders('GOALS_CONFIG').map(function(h) { return String(h).trim(); });
    var areaCol = headers.indexOf('Area');
    if (areaCol >= 0) {   // -1 = legacy header / not yet migrated — no overrides yet, safe no-op
      getTabData('GOALS_CONFIG').forEach(function(row) {
        var areaName = String(row[areaCol] || '').trim();
        if (!areaName) return;
        var rec = {};
        headers.forEach(function(h, idx) {
          if (idx === areaCol || !h) return;
          var val = parseFloat(row[idx]);
          if (!isNaN(val) && val > 0) rec[h] = val;
        });
        byArea[areaName] = rec;
      });
    }
  } catch (e) {
    Logger.log('Agent2: GOALS_CONFIG read failed, using mission defaults only — ' + e.message);
  }

  return {
    missionDefaults: missionDefaults,
    forArea: function(areaName, metricKey) {
      var rec = byArea[areaName];
      if (rec && rec[metricKey] > 0) return rec[metricKey];
      return missionDefaults[metricKey] || 0;
    }
  };
}

/**
 * Reads DAILY_LOG and sums metric values per area per transfer period.
 * Returns { areaName: { metric_key: [t1Sum, t2Sum, t3Sum] } }
 * Areas with zero submissions in all periods still appear if they exist in DAILY_LOG.
 */
function a2_loadDailyLog(transfers, metrics) {
  var headers = getTabHeaders('DAILY_LOG').map(function(h) { return String(h).trim(); });
  var data    = getTabData('DAILY_LOG');
  var result  = {};

  if (!data || data.length === 0) return result;

  var dateCol = headers.indexOf('Date');
  var areaCol = headers.indexOf('Area');
  if (dateCol < 0 || areaCol < 0) return result;

  var metricCols = {};
  metrics.forEach(function(m) {
    var idx = headers.indexOf(m['Metric_Key']);
    if (idx >= 0) metricCols[m['Metric_Key']] = idx;
  });

  data.forEach(function(row) {
    var dateStr = a2_toDateString(row[dateCol]);
    if (!dateStr) return;
    var area = String(row[areaCol] || '').trim();
    if (!area) return;

    var rowDate = a2_parseDate(dateStr);

    // Find which transfer window this row falls into
    var tIdx = -1;
    for (var i = 0; i < transfers.length; i++) {
      if (rowDate >= transfers[i].start && rowDate <= transfers[i].end) {
        tIdx = i; break;
      }
    }
    if (tIdx < 0) return;

    if (!result[area]) result[area] = {};

    metrics.forEach(function(m) {
      var key = m['Metric_Key'];
      if (!result[area][key]) result[area][key] = [0, 0, 0];
      var ci = metricCols[key];
      if (ci !== undefined) {
        result[area][key][tIdx] += (parseFloat(row[ci]) || 0);
      }
    });
  });

  return result;
}

// ─── ANALYSIS ─────────────────────────────────────────────────────────────────

/**
 * Runs per-area per-metric analysis across all non-leadership MISSION_ORG areas.
 * Returns array of analysis result objects, one per area per metric.
 */
function a2_analyzeAllAreas(missionOrg, logData, metrics, goals, transfers) {
  var results = [];
  var today   = a2_todayString();

  missionOrg.forEach(function(area) {
    if (a2_isLeadershipRow(area)) return;  // leaders don't submit

    var areaName  = area['Area_Name'];
    var areaLogData = logData[areaName] || {};

    metrics.forEach(function(m) {
      var key         = m['Metric_Key'];
      var currentGoal = goals.forArea(areaName, key);
      var sums        = areaLogData[key] || [0, 0, 0];

      // Weekly averages per transfer (null if no data exists for that period)
      var avgT1 = sums[0] / transfers[0].weeks;
      var avgT2 = (sums[1] > 0 || logData[areaName]) ? sums[1] / transfers[1].weeks : null;
      var avgT3 = (sums[2] > 0 || logData[areaName]) ? sums[2] / transfers[2].weeks : null;

      var trend        = a2_determineTrend([avgT1, avgT2, avgT3], currentGoal);
      var suggestedGoal = a2_suggestGoal(avgT1, currentGoal, trend);

      results.push({
        analysisDate:  today,
        areaName:      areaName,
        zone:          area['Zone']     || '',
        district:      area['District'] || '',
        metricKey:     key,
        displayName:   m['Metric_Display_Name'],
        currentGoal:   currentGoal,
        avgT1:         Math.round(avgT1 * 10) / 10,
        avgT2:         avgT2 !== null ? Math.round(avgT2 * 10) / 10 : null,
        avgT3:         avgT3 !== null ? Math.round(avgT3 * 10) / 10 : null,
        trend:         trend,
        suggestedGoal: suggestedGoal
      });
    });
  });

  return results;
}

/**
 * Determines trend for one area + metric based on weekly averages across transfers.
 *
 * Beating Goal  — T1 avg >= current goal (only meaningful if goal > 0)
 * Improving     — clear upward trajectory across transfers
 * Declining     — clear downward trajectory across transfers
 * Inconsistent  — no clear pattern, or only 1 transfer of data
 */
function a2_determineTrend(avgs, currentGoal) {
  var t1 = avgs[0];
  var t2 = avgs[1];
  var t3 = avgs[2];

  if (currentGoal > 0 && t1 >= currentGoal) return 'Beating Goal';

  // Not enough history for directional trend
  if (t2 === null || t2 === 0 && t3 === null) return 'Inconsistent';

  var THRESHOLD = 0.10;  // 10% swing to count as directional

  var up12   = t1 > t2 * (1 + THRESHOLD);
  var down12 = t1 < t2 * (1 - THRESHOLD);

  if (t3 === null) {
    if (up12)   return 'Improving';
    if (down12) return 'Declining';
    return 'Inconsistent';
  }

  var up23   = t2 > t3 * (1 + THRESHOLD);
  var down23 = t2 < t3 * (1 - THRESHOLD);

  if (up12 && (up23 || t2 >= t3))   return 'Improving';
  if (down12 && (down23 || t2 <= t3)) return 'Declining';
  return 'Inconsistent';
}

/**
 * Suggests a new weekly goal for the next transfer.
 *   Beating Goal: avg × 1.05 (stretch slightly)
 *   Below Goal:   avg × 1.10 (bigger push)
 *   Cap:          current_goal × 1.5
 * Returns 0 if no meaningful data exists.
 */
function a2_suggestGoal(avgT1, currentGoal, trend) {
  if (avgT1 <= 0 && currentGoal <= 0) return 0;

  var base       = avgT1 > 0 ? avgT1 : currentGoal;
  var multiplier = (trend === 'Beating Goal') ? 1.05 : 1.10;
  var suggested  = base * multiplier;
  var cap        = currentGoal > 0 ? currentGoal * 1.5 : suggested;

  suggested = Math.min(suggested, cap);
  return Math.round(suggested * 10) / 10;
}

// ─── GOAL_RECALIBRATION TAB ───────────────────────────────────────────────────

/**
 * Overwrites GOAL_RECALIBRATION with the full per-area per-metric analysis.
 * Writes a header row if the tab is empty, then all analysis rows. This is
 * the self-initialization CcsmData.gs's CCSM_TAB_SPECS expects (the tab is
 * built with headers: null — this agent writes its own header on first run).
 * Returns the number of data rows written.
 */
function a2_writeGoalRecalibration(analysisRows, metrics, transfers) {
  var sheet = getTab('GOAL_RECALIBRATION');

  var header = [
    'Analysis_Date', 'Area', 'Zone', 'District',
    'Metric_Key', 'Metric_Display_Name', 'Current_Goal',
    'Avg_Week_T1 (' + transfers[0].label + ')',
    transfers.length > 1 ? 'Avg_Week_T2 (' + transfers[1].label + ')' : 'Avg_Week_T2',
    transfers.length > 2 ? 'Avg_Week_T3 (' + transfers[2].label + ')' : 'Avg_Week_T3',
    'Trend', 'Suggested_Goal'
  ];

  var rows = [header];

  analysisRows.forEach(function(r) {
    rows.push([
      r.analysisDate,
      r.areaName,
      r.zone,
      r.district,
      r.metricKey,
      r.displayName,
      r.currentGoal,
      r.avgT1,
      r.avgT2 !== null ? r.avgT2 : '',
      r.avgT3 !== null ? r.avgT3 : '',
      r.trend,
      r.suggestedGoal
    ]);
  });

  // Overwrite rows 2+ (preserves row 1 header from buildSheetSkeleton if present)
  var lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).clearContent();
  }

  if (rows.length > 0) {
    // If tab is empty, write our header to row 1 first
    if (lastRow === 0) {
      sheet.appendRow(header);
      rows.shift();  // remove header — already written
    }
    if (rows.length > 0) {
      sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
    }
  }

  SpreadsheetApp.flush();
  return analysisRows.length;
}

// ─── UTILITIES ────────────────────────────────────────────────────────────────

// IMPORTANT: this must key off Area_Name, not the Is_ZL/Is_STL/Is_DL/Is_AP/
// Is_MP flags. A REAL teaching-area row can legitimately have one of those
// flags set TRUE too — whenever that area's companion currently holds a
// leadership calling. Checking the flags would wrongly exclude that area
// from goal recalibration entirely (mirrors CCSM_Agent3.gs's
// a3_isLeadershipRow). IMOS role titles (Mission President, Zone Leader,
// District Leader, etc.) are standard English across all missions regardless
// of the mission's working language, so this pattern is unchanged from the
// Provo original.
function a2_isLeadershipRow(areaObj) {
  var name = (areaObj['Area_Name'] || '').trim();
  return /^(Mission President|Assistant to President|Zone Leader|Sister Training Leader -|District Leader -)/i.test(name);
}

function a2_todayString() {
  return Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd');
}

function a2_toDateString(val) {
  if (val === null || val === undefined || val === '') return null;
  // yyyy-MM-dd strings are taken literally — new Date('yyyy-MM-dd') parses as
  // UTC midnight, which is the PREVIOUS day in the mission's local timezone.
  if (typeof val === 'string') {
    var m = val.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return m[1] + '-' + m[2] + '-' + m[3];
  }
  var d;
  if (val instanceof Date)      { d = val; }
  else if (typeof val === 'number') { d = new Date(Date.UTC(1899, 11, 30) + val * 86400000); }
  else                          { d = new Date(String(val).trim()); }
  if (isNaN(d.getTime())) return null;
  return Utilities.formatDate(d, getMissionTimezone(), 'yyyy-MM-dd');
}

function a2_parseDate(dateStr) {
  var p = dateStr.split('-');
  return new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]), 12);
}
