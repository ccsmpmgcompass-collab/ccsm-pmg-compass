/**
 * ============================================================
 * CCSM_Agent3.gs — Daily Refresh Agent
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of Agent3.gs (docs/Agent3.gs in PMG-Compass) for the CCSM Spanish
 * daily-report form. Internal a3_* function names are kept identical to the
 * Provo original so future diffs stay readable; only the form column
 * constants, the special "was this an extra push day?" checkbox logic
 * (deleted — no such question at CCSM), effort/exchanges parsing, timezone
 * source, and the missed-days email templates are changed.
 *
 * SCHEDULE: Every day at 6:00 AM (and again at 9:00 PM via the evening
 *           trigger). Run setupAgent3Trigger() / setupAgent3EveningTrigger()
 *           ONCE to create the triggers. The bound project's timezone is
 *           Santiago (Task 14), so atHour(6)/atHour(21) are already local.
 *
 * WHAT IT DOES:
 *   1. Reads NIGHTLY_FORM_RAW, normalizes area names against MISSION_ORG
 *   2. Appends new rows to DAILY_LOG — one row per area per date, no duplicates
 *   3. Rebuilds LIVE_SNAPSHOT — 7d / 14d / 28d / transfer-to-date totals per area
 *   4. Checks for 2+ consecutive missed days per area; sends pre-written alert
 *      if that exact gap has not already been logged in MISSING_LOG
 *   5. Logs the run result to AGENT_RUN_LOG
 *
 * REQUIRED AGENT_CONFIG KEYS:
 *   TRANSFER_START_DATE  — start of current transfer, format: YYYY-MM-DD
 *   NIGHTLY_FORM_LINK    — full URL of the nightly Google Form
 *   MISSED_DAYS_LOOKBACK — how many days back to scan for gaps (default: 14)
 *
 * ASSUMED COLUMN NAMES — must match your actual sheet headers exactly:
 *   MISSION_ORG:       Area_Name | Zone | District | Companion1_Email | Companion2_Email | ...
 *   QUESTIONS_CONFIG:  Metric_Key | Metric_Display_Name | Form_Column_Header | Form_Type | Data_Type | Active
 *   DAILY_LOG:         Date | Area | Zone | District | [one col per Metric_Key]
 *   LIVE_SNAPSHOT:     Area | Zone | District | Last_Updated | [Key_7d|Key_14d|Key_28d|Key_Transfer per metric]
 *   MISSING_LOG:       Area | Missing_Dates | Message_ID | Notified_Timestamp | Email_Sent_To
 *   MESSAGE_BANK:      Message_ID | Category | Metric | Subcategory | Subject_Line | Body_Text | PMG_Chapter | PMG_Description | Scripture | Scripture_Text | Active
 */

// ─── SHEET DATA HELPER ─────────────────────────────────────────────────────
// a3_getSheetData() reads the native Sheet API directly (unlike getTabData()
// in CCSM_Helpers.gs, which skips the header row) because Agent3 needs
// headers for column-name lookup. Returns [] for empty or missing tabs
// rather than throwing.

function a3_getSheetData(tabName) {
  var sheet = getTab(tabName);
  if (!sheet || sheet.getLastRow() === 0) return [];
  return sheet.getDataRange().getValues();
}

// ─── FORM COLUMN CONSTANTS ──────────────────────────────────────────────────
// Must match the exact question text in the CCSM Spanish Google Form
// (DailyReportForm_ES.gs / CcsmData.gs CCSM_FORM_STRUCTURAL).

var A3_FORM_AREA_COL = '¿En qué área sirve?';        // repeated once per zone section
var A3_FORM_ZONE_COL = '¿En qué zona sirve?';        // single global column
var A3_FORM_DATE_COL = '¿Qué fecha está ingresando?'; // repeated once per zone section
// Note: the CCSM nightly form has no "extra push day" style checkbox
// question — that entire concept from the Provo original is deleted here.

// ─── MAIN ENTRY POINT ────────────────────────────────────────────────────────

/**
 * Called by the daily time trigger.
 * Runs all four steps and logs the result regardless of errors in any step.
 */
function runAgent3() {
  var status = 'SUCCESS';
  var notes  = [];

  try {
    Logger.log('Agent3: Starting daily refresh — ' + new Date().toISOString());

    // Load shared reference data once — all steps below use these
    var missionOrg    = a3_loadMissionOrg();
    var areaLookup    = a3_buildAreaLookup(missionOrg);  // lowercase -> canonical name
    var metrics       = a3_loadActiveMetrics();           // active NIGHTLY metrics only
    var transferStart = getConfig('TRANSFER_START_DATE'); // 'YYYY-MM-DD'
    var lookbackDays  = parseInt(getConfig('MISSED_DAYS_LOOKBACK') || '14');
    var formLink      = getConfig('NIGHTLY_FORM_LINK') || '';
    // 3+ TOTAL missing days (in the lookback window, excluding today) escalates
    // the alert to the area's District Leader. Override via AGENT_CONFIG.
    var escalateThreshold = parseInt(getConfig('MISSED_DAYS_ESCALATE_THRESHOLD') || '3');

    if (!transferStart) throw new Error('AGENT_CONFIG is missing TRANSFER_START_DATE');
    if (metrics.length === 0) throw new Error('No active NIGHTLY metrics found in QUESTIONS_CONFIG');

    // Read raw form data once — shared by multiple steps
    var nightlyRaw = a3_getSheetData('NIGHTLY_FORM_RAW');

    // Steps 1+2: Parse form rows and append new dates to DAILY_LOG
    var dailyRecords = a3_buildDailyRecords(nightlyRaw, areaLookup, metrics);
    var newRows      = a3_updateDailyLog(dailyRecords, missionOrg, metrics);
    notes.push('DAILY_LOG: ' + newRows + ' new row(s)');

    // Step 3: Rebuild LIVE_SNAPSHOT from full DAILY_LOG history
    var snapshotCount = a3_buildLiveSnapshot(missionOrg, metrics, transferStart);
    notes.push('LIVE_SNAPSHOT: rebuilt for ' + snapshotCount + ' area(s)');

    // Step 4: Missed-days check and alerts
    // Wrapped separately so an email quota error doesn't abort DAILY_LOG / LIVE_SNAPSHOT
    var alertsSent = 0;
    try {
      alertsSent = a3_checkMissedDays(missionOrg, nightlyRaw, areaLookup, lookbackDays, formLink, escalateThreshold, transferStart);
    } catch (emailErr) {
      notes.push('MISSED_DAYS ERROR: ' + emailErr.message);
      Logger.log('Agent3: missed-days step failed — ' + emailErr.message);
    }
    notes.push('MISSED_DAYS: ' + alertsSent + ' alert(s) sent');

    Logger.log('Agent3: Complete — ' + notes.join(' | '));

  } catch (e) {
    status = 'ERROR';
    notes.push('ERROR: ' + e.message);
    Logger.log('Agent3 FATAL: ' + e.message + '\n' + (e.stack || ''));
  }

  // logRun(agent, status, recordsProcessed, emailsSent, durationMs, notes, error)
  logRun('Agent3', status, null, null, null, notes.join(' | '));
}

// ─── TRIGGER SETUP ───────────────────────────────────────────────────────────

/**
 * Creates the daily 6 AM trigger for Agent3.
 * Run this ONCE: Apps Script editor -> Run -> setupAgent3Trigger
 * Safe to re-run — deletes any existing Agent3 trigger first.
 */
function setupAgent3Trigger() {
  deleteTriggerByName('runAgent3');
  ScriptApp.newTrigger('runAgent3')
    .timeBased()
    .everyDays(1)
    .atHour(6)
    .create();
  Logger.log('Agent3 trigger created: runAgent3 daily at 6 AM');
}

// ─── DATA LOADERS ─────────────────────────────────────────────────────────────

/**
 * Loads all rows from MISSION_ORG as an array of plain objects keyed by header name.
 * Skips blank rows. Requires columns: Area_Name, Zone, District, Active.
 */
function a3_loadMissionOrg() {
  var data = a3_getSheetData('MISSION_ORG');
  if (!data || data.length < 2) throw new Error('MISSION_ORG is empty or missing headers');

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var areas   = [];

  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    var obj = {};
    headers.forEach(function(h, idx) {
      obj[h] = (row[idx] != null) ? String(row[idx]).trim() : '';
    });
    var isActive = obj['Active'] && obj['Active'].toUpperCase() === 'TRUE';
    if (obj['Area_Name'] && isActive) areas.push(obj);
  }

  if (areas.length === 0) throw new Error('MISSION_ORG has no data rows — check Active column values');
  return areas;
}

/**
 * Returns a map of lowercase area name -> canonical area name from MISSION_ORG.
 * Used to normalize the free-text area names missionaries type in the form.
 */
function a3_buildAreaLookup(missionOrg) {
  var lookup = {};
  missionOrg.forEach(function(a) {
    if (a['Area_Name']) lookup[a['Area_Name'].toLowerCase()] = a['Area_Name'];
  });
  return lookup;
}

/**
 * Loads active metrics for the nightly form from QUESTIONS_CONFIG.
 * Returns only rows where Active=TRUE and Form_Type=NIGHTLY (or blank = applies to both forms).
 * Excludes the report_date metric — that column drives A3_FORM_DATE_COL / the
 * DAILY_LOG 'Date' column directly and is not itself a per-area metric column.
 * Each returned object has at minimum: Metric_Key, Metric_Display_Name,
 * Form_Column_Header, Form_Type, Data_Type, Active.
 */
function a3_loadActiveMetrics() {
  var data = a3_getSheetData('QUESTIONS_CONFIG');
  if (!data || data.length < 2) throw new Error('QUESTIONS_CONFIG has no data rows — add metric rows below the header');

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var metrics = [];

  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    var m   = {};
    headers.forEach(function(h, idx) {
      m[h] = (row[idx] != null) ? String(row[idx]).trim() : '';
    });

    var isActive  = m['Active'] && m['Active'].toUpperCase() === 'TRUE';
    var formType  = m['Form_Type'] ? m['Form_Type'].toUpperCase() : '';
    var isNightly = (formType === 'NIGHTLY' || formType === '');
    var isDateCol = m['Metric_Key'] === 'report_date';

    if (isActive && isNightly && !isDateCol && m['Metric_Key'] && m['Form_Column_Header']) {
      metrics.push(m);
    }
  }

  return metrics;
}

// ─── STEPS 1+2: FORM DATA -> DAILY_LOG ───────────────────────────────────────

/**
 * Analyzes NIGHTLY_FORM_RAW headers and returns the section structure.
 *
 * The nightly form is split into sections — one per zone. Each section repeats
 * the same questions ("¿En qué área sirve?", metric columns, "¿Qué fecha está
 * ingresando?", etc.). A missionary fills only their zone's section; all other
 * section columns are blank for that row.
 *
 * Returns an object with:
 *   areaCols      — array of column indices where "¿En qué área sirve?" appears
 *   zoneIdx       — column index of "¿En qué zona sirve?" (global, not per-section)
 *   dateOffset    — offset from a section's area column to its date column
 *   metricOffsets — {Metric_Key: offset} from section start for each active metric
 */
/**
 * Normalizes a form header for matching: lowercase, trimmed, collapsed
 * whitespace, apostrophes stripped. Guards against small wording drift
 * between QUESTIONS_CONFIG and the live form sheet header.
 */
function a3_normHeader(h) {
  return String(h).toLowerCase().replace(/['’]/g, '').replace(/\s+/g, ' ').trim();
}

/**
 * Known QUESTIONS_CONFIG -> live-form header variants (normalized form).
 * CCSM's QUESTIONS_CONFIG is generated from the same CcsmData.gs source as
 * the form itself (BuildCcsmSheet.gs / DailyReportForm_ES.gs both read
 * CCSM_NIGHTLY_QUESTIONS), so no drift exists yet. The mechanism is kept for
 * future fixes if the two are ever edited independently.
 */
function a3_headerAlias(normalizedConfigHeader) {
  return null;
}

function a3_parseSectionStructure(headers, metrics) {
  var areaTarget = a3_normHeader(A3_FORM_AREA_COL);
  var zoneTarget = a3_normHeader(A3_FORM_ZONE_COL);
  var dateTarget = a3_normHeader(A3_FORM_DATE_COL);

  var areaCols = [];
  var zoneIdx  = -1;

  headers.forEach(function(h, idx) {
    var norm = a3_normHeader(h);
    if (norm === areaTarget) areaCols.push(idx);
    if (norm === zoneTarget && zoneIdx < 0) zoneIdx = idx;
  });

  if (areaCols.length === 0) throw new Error(
    'NIGHTLY_FORM_RAW: no column matching "' + A3_FORM_AREA_COL + '" found. ' +
    'Check A3_FORM_AREA_COL constant at the top of CCSM_Agent3.gs.'
  );

  // Use the first section as the template to learn column offsets
  var sectionStart = areaCols[0];
  var sectionEnd   = areaCols.length > 1 ? areaCols[1] : headers.length;

  // Build normalized-header -> offset map for within-section lookups
  var offsetByHeader = {};
  for (var i = sectionStart; i < sectionEnd; i++) {
    var h = a3_normHeader(headers[i]);
    if (!(h in offsetByHeader)) offsetByHeader[h] = i - sectionStart;
  }

  var dateOffset = offsetByHeader[dateTarget];
  if (dateOffset === undefined) throw new Error(
    'NIGHTLY_FORM_RAW: cannot find "' + A3_FORM_DATE_COL + '" within a section. ' +
    'Check A3_FORM_DATE_COL constant.'
  );

  // Map active metrics to their within-section offsets.
  // Questions added to the form AFTER launch get their response columns
  // APPENDED to the far right of the sheet — one column per zone section,
  // OUTSIDE every section's column range. For any metric not found inside
  // the section template, fall back to a global search and record every
  // matching column index; the row parser combines whichever of those
  // copies the missionary filled.
  var metricOffsets    = {};
  var globalMetricCols = {};
  metrics.forEach(function(m) {
    var colNorm = a3_normHeader(m['Form_Column_Header']);
    var alias   = a3_headerAlias(colNorm);

    var offset = offsetByHeader[colNorm];
    if (offset === undefined && alias) offset = offsetByHeader[alias];
    if (offset !== undefined) {
      metricOffsets[m['Metric_Key']] = offset;
      return;
    }

    var globalCols = [];
    headers.forEach(function(h, idx) {
      var hn = a3_normHeader(h);
      if (hn === colNorm || (alias && hn === alias)) globalCols.push(idx);
    });
    if (globalCols.length > 0) {
      globalMetricCols[m['Metric_Key']] = globalCols;
      Logger.log('Agent3: metric "' + m['Metric_Key'] + '" not in section template — using ' +
                 globalCols.length + ' appended column(s) at ' + globalCols.join(','));
    } else {
      Logger.log('Agent3 WARNING: "' + m['Form_Column_Header'] +
                 '" not found anywhere in NIGHTLY_FORM_RAW — check QUESTIONS_CONFIG Form_Column_Header.');
    }
  });

  return { areaCols: areaCols, zoneIdx: zoneIdx, dateOffset: dateOffset,
           metricOffsets: metricOffsets, globalMetricCols: globalMetricCols };
}

/**
 * Parses every row in NIGHTLY_FORM_RAW into a map of "Area|YYYY-MM-DD" -> record.
 *
 * Key behavior:
 * - Handles the multi-section form structure (one section per zone). Finds which
 *   section a missionary filled by locating the non-blank "¿En qué área sirve?" column.
 * - Uses the missionary-entered date field, NOT the form submission timestamp.
 *   This correctly handles backfilled submissions for past missed days.
 * - If the same area submits multiple rows for the same date:
 *     NUMBER metrics are SUMMED.
 *     YESNO metrics ('exchanges': Sí/No) are OR'd — 'TRUE' if ANY submission said Sí,
 *       stored as 'TRUE'/'' in DAILY_LOG.
 *     CHOICE metrics ('effort': Todo/La mayor parte/Algo) keep the last non-blank
 *       raw Spanish value, stored as-is in DAILY_LOG (see ccsmEffortScore() in
 *       CCSM_Helpers.gs for agents that need a numeric equivalent).
 * - Rows with unrecognized area names or invalid dates are skipped with a log warning.
 */
function a3_buildDailyRecords(nightlyRaw, areaLookup, metrics) {
  var records = {};
  if (!nightlyRaw || nightlyRaw.length < 2) return records;

  var headers     = nightlyRaw[0].map(function(h) { return String(h).trim(); });
  var sectionInfo = a3_parseSectionStructure(headers, metrics);

  for (var i = 1; i < nightlyRaw.length; i++) {
    var row = nightlyRaw[i];

    // Find which section is filled — the one whose area column is non-blank
    var sectionStart = -1;
    var rawArea      = '';
    for (var s = 0; s < sectionInfo.areaCols.length; s++) {
      var val = String(row[sectionInfo.areaCols[s]] || '').trim();
      if (val) { sectionStart = sectionInfo.areaCols[s]; rawArea = val; break; }
    }
    if (!rawArea) continue;

    var canonArea = areaLookup[rawArea.toLowerCase()];
    if (!canonArea) {
      Logger.log('Agent3: Unrecognized area "' + rawArea + '" in row ' + (i + 1) + ' — skipped');
      continue;
    }

    var rawDate = row[sectionStart + sectionInfo.dateOffset];
    var dateStr = a3_toDateString(rawDate);
    if (!dateStr) {
      Logger.log('Agent3: Invalid date in row ' + (i + 1) + ' for "' + rawArea + '" — skipped');
      continue;
    }

    var rawZone = sectionInfo.zoneIdx >= 0 ? String(row[sectionInfo.zoneIdx] || '').trim() : '';
    var key     = canonArea + '|' + dateStr;

    if (!records[key]) {
      records[key] = { area: canonArea, zone: rawZone, date: dateStr, totals: {} };
      metrics.forEach(function(m) {
        var dt = m['Data_Type'];
        records[key].totals[m['Metric_Key']] = (dt === 'YESNO' || dt === 'CHOICE') ? '' : 0;
      });
    }

    metrics.forEach(function(m) {
      var metricKey = m['Metric_Key'];
      var dataType  = m['Data_Type'];
      var offset    = sectionInfo.metricOffsets[metricKey];

      var rawValues = [];
      if (offset !== undefined) {
        rawValues.push(row[sectionStart + offset]);
      } else {
        var globalCols = sectionInfo.globalMetricCols[metricKey];
        if (globalCols) {
          globalCols.forEach(function(ci) { rawValues.push(row[ci]); });
        }
      }
      if (rawValues.length === 0) return;

      if (dataType === 'YESNO') {
        // OR logic: if any submission for this area+date says Sí, mark true.
        var isYes = rawValues.some(function(v) { return String(v || '').trim() === 'Sí'; });
        if (isYes) records[key].totals[metricKey] = 'TRUE';
      } else if (dataType === 'CHOICE') {
        // Last non-blank raw value wins.
        for (var vi = rawValues.length - 1; vi >= 0; vi--) {
          var cv = String(rawValues[vi] || '').trim();
          if (cv) { records[key].totals[metricKey] = cv; break; }
        }
      } else {
        rawValues.forEach(function(v) {
          records[key].totals[metricKey] += (parseFloat(v) || 0);
        });
      }
    });
  }

  return records;
}

/**
 * Appends new Area+Date records to DAILY_LOG. Skips any combo already present.
 *
 * DAILY_LOG column order: Date | Area | Zone | District | [one column per Metric_Key]
 *
 * If DAILY_LOG has no header row yet, writes one first.
 * Uses a single batch setValues() call for performance.
 * Returns the number of new rows written.
 */
function a3_updateDailyLog(dailyRecords, missionOrg, metrics) {
  var sheet      = getTab('DAILY_LOG');
  var lastRow    = sheet.getLastRow();
  var existing   = {};
  var hasHeaders = lastRow > 0;

  if (hasHeaders) {
    var sheetData  = sheet.getDataRange().getValues();
    var logHeaders = sheetData[0].map(function(h) { return String(h).trim(); });
    var areaCol    = logHeaders.indexOf('Area');
    var dateCol    = logHeaders.indexOf('Date');

    for (var i = 1; i < sheetData.length; i++) {
      var area = String(sheetData[i][areaCol] || '').trim();
      var date = a3_toDateString(sheetData[i][dateCol]);
      if (area && date) existing[area + '|' + date] = true;
    }
  }

  // Build district lookup for enriching new rows
  var districtMap = {};
  missionOrg.forEach(function(a) { districtMap[a['Area_Name']] = a['District'] || ''; });

  // Collect all new rows, sorted by date+area for clean ordering in the log
  var newRows = [];
  Object.keys(dailyRecords).sort().forEach(function(key) {
    if (existing[key]) return;
    var rec = dailyRecords[key];
    var row = [rec.date, rec.area, rec.zone, districtMap[rec.area] || ''];
    metrics.forEach(function(m) {
      var v = rec.totals[m['Metric_Key']];
      row.push(v !== undefined ? v : 0);
    });
    newRows.push(row);
  });

  if (newRows.length === 0) return 0;

  // Write header row first if the tab was empty
  if (!hasHeaders) {
    var headerRow = ['Date', 'Area', 'Zone', 'District'];
    metrics.forEach(function(m) { headerRow.push(m['Metric_Key']); });
    sheet.appendRow(headerRow);
  }

  // Batch-write all new rows in one API call (much faster than looping appendRow)
  var startRow = sheet.getLastRow() + 1;
  sheet.getRange(startRow, 1, newRows.length, newRows[0].length).setValues(newRows);

  return newRows.length;
}

// ─── STEP 3: LIVE_SNAPSHOT ─────────────────────────────────────────────────

/**
 * Completely rebuilds LIVE_SNAPSHOT from the full DAILY_LOG history.
 * One row per area in MISSION_ORG, showing rolling totals for four windows:
 *   7d       = last 7 calendar days (includes today)
 *   14d      = last 14 calendar days
 *   28d      = last 28 calendar days
 *   transfer = from TRANSFER_START_DATE through today
 *
 * Column order: Area | Zone | District | Last_Updated |
 *               [Key_7d | Key_14d | Key_28d | Key_Transfer per active metric]
 *
 * Non-numeric metrics (exchanges/effort) parse to 0 in every window here —
 * DAILY_LOG stores them as 'TRUE'/''/'Todo' text, not running totals. That's
 * expected: rolling sums of a Sí/No or Todo/Algo answer aren't meaningful:
 * agents that need a numeric read of effort use ccsmEffortScore() directly
 * against DAILY_LOG rows instead of LIVE_SNAPSHOT.
 *
 * Overwrites the tab completely on each run via overwriteTab() from CCSM_Helpers.gs.
 */
function a3_buildLiveSnapshot(missionOrg, metrics, transferStartStr) {
  var logData = a3_getSheetData('DAILY_LOG');

  // Cutoff dates for each window — local midnight so date comparisons are clean
  var today  = new Date();
  today.setHours(0, 0, 0, 0);
  var cut7d  = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 7);
  var cut14d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 14);
  var cut28d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 28);

  // TRANSFER_START_DATE may arrive as a stringified Date object because
  // AGENT_CONFIG date cells return Date objects from getValues(). Normalize
  // to yyyy-MM-dd first via a3_toDateString.
  var xfrNorm = a3_toDateString(transferStartStr);
  if (!xfrNorm) throw new Error('TRANSFER_START_DATE is not a valid date: "' + transferStartStr + '"');
  var cutXfr = a3_parseLocalDate(xfrNorm);

  // Index DAILY_LOG rows by area name -> [{date: Date, totals: {key: value}}]
  var logByArea = {};

  if (logData && logData.length > 1) {
    var logHeaders   = logData[0].map(function(h) { return String(h).trim(); });
    var areaCol      = logHeaders.indexOf('Area');
    var dateCol      = logHeaders.indexOf('Date');

    // Map Metric_Key -> column index in DAILY_LOG.
    var metricColIdx = {};
    metrics.forEach(function(m) {
      var key = m['Metric_Key'];
      var idx = logHeaders.indexOf(key);
      if (idx < 0) idx = logHeaders.indexOf(a3_legacyMetricAlias(key));
      if (idx >= 0) metricColIdx[key] = idx;
      else Logger.log('Agent3 WARNING: DAILY_LOG has no column for metric "' + key + '" — totals will be 0.');
    });

    for (var i = 1; i < logData.length; i++) {
      var row     = logData[i];
      var area    = String(row[areaCol] || '').trim();
      var dateStr = a3_toDateString(row[dateCol]);
      if (!area || !dateStr) continue;

      var totals = {};
      metrics.forEach(function(m) {
        var ci = metricColIdx[m['Metric_Key']];
        totals[m['Metric_Key']] = (ci !== undefined) ? (parseFloat(row[ci]) || 0) : 0;
      });

      if (!logByArea[area]) logByArea[area] = [];
      logByArea[area].push({ date: a3_parseLocalDate(dateStr), totals: totals });
    }
  }

  // Build header row
  var headerRow = ['Area', 'Zone', 'District', 'Last_Updated'];
  metrics.forEach(function(m) {
    headerRow.push(m['Metric_Key'] + '_7d');
    headerRow.push(m['Metric_Key'] + '_14d');
    headerRow.push(m['Metric_Key'] + '_28d');
    headerRow.push(m['Metric_Key'] + '_transfer');
  });

  var lastUpdated = Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd HH:mm');
  var outputRows  = [headerRow];

  missionOrg.forEach(function(areaObj) {
    // Skip all leadership roles — they are in MISSION_ORG for email routing only, not as
    // submitting areas. Zone=ALL catches MP/APs; Is_ZL/STL/DL catches zone+district leaders
    // who have real zone names but no submitted form data.
    if (a3_isLeadershipRow(areaObj)) return;

    var areaName    = areaObj['Area_Name'];
    var submissions = logByArea[areaName] || [];
    var row         = [areaName, areaObj['Zone'] || '', areaObj['District'] || '', lastUpdated];

    metrics.forEach(function(m) {
      var key = m['Metric_Key'];
      var t7 = 0, t14 = 0, t28 = 0, tXfr = 0;

      submissions.forEach(function(s) {
        var val = s.totals[key] || 0;
        if (s.date >= cut7d)  t7   += val;
        if (s.date >= cut14d) t14  += val;
        if (s.date >= cut28d) t28  += val;
        if (s.date >= cutXfr) tXfr += val;
      });

      row.push(t7, t14, t28, tXfr);
    });

    outputRows.push(row);
  });

  overwriteTab('LIVE_SNAPSHOT', outputRows);
  return outputRows.length - 1;  // data rows only (excludes header)
}

// ─── STEP 4: MISSED-DAYS CHECKER ───────────────────────────────────────────

/**
 * For each area, checks if there are 2+ consecutive calendar days with no submission
 * within the past `lookbackDays` days.
 *
 * Sends a pre-written MISSED_DAYS alert only if:
 *   (a) there is a consecutive gap of 2+ days, AND
 *   (b) that exact set of dates has not already been logged in MISSING_LOG
 *
 * The gap key is "Area|date1,date2,..." — if a gap grows (new day added), it becomes
 * a new key and a new alert fires. This intentionally nudges areas that keep missing days.
 *
 * Returns total number of alerts sent.
 */
function a3_checkMissedDays(missionOrg, nightlyRaw, areaLookup, lookbackDays, formLink, escalateThreshold, transferStart) {
  escalateThreshold = escalateThreshold || 3;

  var today = new Date();
  today.setHours(0, 0, 0, 0);

  var submittedDates  = a3_buildSubmissionDateMap(nightlyRaw, areaLookup);
  var alreadyNotified = a3_loadAlreadyNotified();          // { companionship:{}, escalation:{} }
  var missedMsgs      = a3_loadMissedDayMessages();
  var dlLookup        = a3_buildDistrictLeaderLookup(missionOrg); // district(lowercase) -> emails

  if (missedMsgs.length === 0) {
    Logger.log('Agent3: No active MISSED_DAYS messages in MESSAGE_BANK. Skipping alerts.');
    return 0;
  }

  var alertsSent = 0;
  var nowStr = Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd HH:mm');

  missionOrg.forEach(function(areaObj) {
    var areaName = areaObj['Area_Name'];

    // Skip all leadership roles — ZLs/STLs/DLs have real zone names but don't submit
    // the nightly form as an area and should never receive missed-day alerts
    if (a3_isLeadershipRow(areaObj)) return;

    // Companion emails — skip blanks and placeholder addresses (notreadyyet, TBD)
    var email = [areaObj['Companion1_Email'], areaObj['Companion2_Email']]
      .filter(function(e) {
        if (!e || !e.trim()) return false;
        var lower = e.toLowerCase();
        return lower.indexOf('notreadyyet') < 0 && lower.indexOf('tbd@') < 0;
      })
      .join(',');

    var missingDates = a3_getMissingDates(areaName, submittedDates, today, lookbackDays, transferStart);
    if (missingDates.length === 0) return;

    // ── Tier 1: companionship reminder on a 2+ CONSECUTIVE missed-day gap ──────
    if (email) {
      var gaps = a3_findConsecutiveGaps(missingDates);
      gaps.forEach(function(gap) {
        var gapKey = areaName + '|' + gap.join(',');
        if (alreadyNotified.companionship[gapKey]) return;  // already alerted this exact gap

        var msg = missedMsgs[Math.floor(Math.random() * missedMsgs.length)];
        var parts = gap.map(function(d) { return a3_formatReadableDate(d); });
        var dateList = parts.length === 1
          ? parts[0]
          : parts.slice(0, -1).join(', ') + ' y ' + parts[parts.length - 1];

        var subject  = a3_injectVars(msg['Subject_Line'], areaName, dateList, formLink);
        var bodyText = a3_injectVars(msg['Body_Text'],    areaName, dateList, formLink);
        var body     = a3_buildMissedDaysHtml(bodyText, formLink);

        sendEmail(email, subject, body, 'Agent3');

        // Write by header NAME so dedup keeps working even if MISSING_LOG columns
        // are reordered.
        a3_appendMissingLog({
          'Area':               areaName,
          'Message_ID':         msg['Message_ID'],
          'Notified_Timestamp': nowStr,
          'Email_Sent_To':      email,
          'Missing_Dates':      gap.join(','),
          'Days_Missed_Count':  gap.length,
          'Alert_Status':       'NOTIFIED'
        });

        alreadyNotified.companionship[gapKey] = true;
        alertsSent++;
        Logger.log('Agent3: Reminder -> ' + areaName + ' (' + email + ') | Missing: ' + gap.join(', '));
      });
    }

    // ── Tier 2: escalate to the District Leader on 3+ TOTAL missed days ────────
    // "Total" = count of missed days in the lookback window, excluding today
    // (a3_getMissingDates already starts at yesterday). Not necessarily consecutive.
    if (missingDates.length >= escalateThreshold) {
      var escKey = areaName + '|' + missingDates.join(',');
      if (!alreadyNotified.escalation[escKey]) {
        var district = String(areaObj['District'] || '').trim().toLowerCase();
        var dlEmail  = dlLookup[district];
        if (dlEmail) {
          var escSubject = 'Alerta de Informes Faltantes — ' + areaName;
          var escBody    = a3_buildEscalationHtml(areaName, missingDates, missingDates.length, formLink);

          sendEmail(dlEmail, escSubject, escBody, 'Agent3');

          a3_appendMissingLog({
            'Area':                 areaName,
            'Message_ID':           'DL-ESCALATION',
            'Missing_Dates':        missingDates.join(','),
            'Days_Missed_Count':    missingDates.length,
            'Alert_Sent_Timestamp': nowStr,
            'Alert_Recipients':     dlEmail,
            'Alert_Status':         'ESCALATED_DL'
          });

          alreadyNotified.escalation[escKey] = true;
          alertsSent++;
          Logger.log('Agent3: ESCALATED -> DL of ' + (areaObj['District'] || '?') +
                     ' (' + dlEmail + ') for ' + areaName + ' | ' + missingDates.length + ' missed');
        } else {
          Logger.log('Agent3: No DL email for district "' + (areaObj['District'] || '') +
                     '" — cannot escalate ' + areaName);
        }
      }
    }
  });

  return alertsSent;
}

/**
 * DRY RUN — logs who WOULD be emailed (companionship reminders + DL escalations)
 * without sending anything or writing to MISSING_LOG.
 *
 * Run from the Apps Script editor: Run -> previewMissedDays, then open
 * View -> Logs to see the list. Use this to verify before trusting a live run.
 */
function previewMissedDays() {
  var missionOrg        = a3_loadMissionOrg();
  var areaLookup        = a3_buildAreaLookup(missionOrg);
  var lookbackDays      = parseInt(getConfig('MISSED_DAYS_LOOKBACK') || '14');
  var escalateThreshold = parseInt(getConfig('MISSED_DAYS_ESCALATE_THRESHOLD') || '3');
  var transferStart     = getConfig('TRANSFER_START_DATE');
  var nightlyRaw        = a3_getSheetData('NIGHTLY_FORM_RAW');
  var submittedDates    = a3_buildSubmissionDateMap(nightlyRaw, areaLookup);
  var alreadyNotified   = a3_loadAlreadyNotified();
  var dlLookup          = a3_buildDistrictLeaderLookup(missionOrg);

  var today = new Date();
  today.setHours(0, 0, 0, 0);

  var comp = [], esc = [];

  missionOrg.forEach(function(areaObj) {
    if (a3_isLeadershipRow(areaObj)) return;
    var areaName = areaObj['Area_Name'];

    var email = [areaObj['Companion1_Email'], areaObj['Companion2_Email']]
      .filter(function(e) {
        if (!e || !e.trim()) return false;
        var l = e.toLowerCase();
        return l.indexOf('notreadyyet') < 0 && l.indexOf('tbd@') < 0;
      }).join(',');

    var missingDates = a3_getMissingDates(areaName, submittedDates, today, lookbackDays, transferStart);
    if (missingDates.length === 0) return;

    if (email) {
      a3_findConsecutiveGaps(missingDates).forEach(function(gap) {
        var k = areaName + '|' + gap.join(',');
        if (!alreadyNotified.companionship[k]) comp.push(areaName + ' -> ' + email + ' | ' + gap.join(','));
      });
    }

    if (missingDates.length >= escalateThreshold) {
      var k = areaName + '|' + missingDates.join(',');
      if (!alreadyNotified.escalation[k]) {
        var dlEmail = dlLookup[String(areaObj['District'] || '').trim().toLowerCase()];
        esc.push(areaName + ' [' + (areaObj['District'] || '') + '] missed ' +
                 missingDates.length + ' -> DL ' + (dlEmail || '(NO DL EMAIL)'));
      }
    }
  });

  Logger.log('=== previewMissedDays (NO emails sent) ===');
  Logger.log('Lookback=' + lookbackDays + ' days | EscalateThreshold=' + escalateThreshold + ' total missed');
  Logger.log('TIER 1 companionship reminders (' + comp.length + '):');
  comp.forEach(function(s) { Logger.log('   ' + s); });
  Logger.log('TIER 2 District Leader escalations (' + esc.length + '):');
  esc.forEach(function(s) { Logger.log('   ' + s); });
  return { companionship: comp, escalation: esc };
}

/**
 * Builds a map of canonical area name -> {dateString: true}
 * from all submission rows in NIGHTLY_FORM_RAW.
 * Uses the missionary-entered date, not the form submission timestamp.
 * Handles the multi-section form structure the same way as a3_buildDailyRecords.
 */
function a3_buildSubmissionDateMap(nightlyRaw, areaLookup) {
  var map = {};
  if (!nightlyRaw || nightlyRaw.length < 2) return map;

  var headers    = nightlyRaw[0].map(function(h) { return String(h).trim(); });
  var areaTarget = A3_FORM_AREA_COL.toLowerCase();
  var dateTarget = A3_FORM_DATE_COL.toLowerCase();

  // Find all area column indices (one per section)
  var areaCols = [];
  headers.forEach(function(h, idx) {
    if (h.toLowerCase() === areaTarget) areaCols.push(idx);
  });
  if (areaCols.length === 0) return map;

  // Find date column offset within the first section
  var sectionStart = areaCols[0];
  var sectionEnd   = areaCols.length > 1 ? areaCols[1] : headers.length;
  var dateOffset   = -1;
  for (var j = sectionStart; j < sectionEnd; j++) {
    if (headers[j].toLowerCase() === dateTarget) { dateOffset = j - sectionStart; break; }
  }
  if (dateOffset < 0) return map;

  for (var i = 1; i < nightlyRaw.length; i++) {
    var row = nightlyRaw[i];

    // Find the filled section
    var filledStart = -1;
    var rawArea     = '';
    for (var s = 0; s < areaCols.length; s++) {
      var val = String(row[areaCols[s]] || '').trim();
      if (val) { filledStart = areaCols[s]; rawArea = val; break; }
    }
    if (!rawArea) continue;

    var canonArea = areaLookup[rawArea.toLowerCase()];
    if (!canonArea) continue;

    var dateStr = a3_toDateString(row[filledStart + dateOffset]);
    if (!dateStr) continue;

    if (!map[canonArea]) map[canonArea] = {};
    map[canonArea][dateStr] = true;
  }

  return map;
}

/**
 * Loads MISSING_LOG and returns two dedup sets of "Area|date1,date2,..." keys:
 *   { companionship: {...}, escalation: {...} }
 *
 * companionship = gaps a reminder was already sent for (Alert_Status != ESCALATED_DL)
 * escalation    = situations already escalated to the District Leader (Alert_Status == ESCALATED_DL)
 *
 * Robust to column misalignment: the date list is located by CONTENT (a
 * YYYY-MM-DD[,YYYY-MM-DD...] pattern) rather than trusting one fixed column.
 */
function a3_loadAlreadyNotified() {
  var result = { companionship: {}, escalation: {} };
  try {
    var data = a3_getSheetData('MISSING_LOG');
    if (!data || data.length < 2) return result;

    var headers   = data[0].map(function(h) { return String(h).trim(); });
    var areaCol   = headers.indexOf('Area');
    var datesCol  = headers.indexOf('Missing_Dates');
    var statusCol = headers.indexOf('Alert_Status');
    if (areaCol < 0) return result;

    var dateListRe = /^\d{4}-\d{2}-\d{2}(,\d{4}-\d{2}-\d{2})*$/;

    for (var i = 1; i < data.length; i++) {
      var row  = data[i];
      var area = String(row[areaCol] || '').trim();
      if (!area) continue;

      // Prefer the named Missing_Dates column; if it doesn't hold a date list
      // (legacy misaligned rows), scan the row for the value that does.
      var dates = '';
      if (datesCol >= 0) {
        var dv = String(row[datesCol] || '').trim();
        if (dateListRe.test(dv)) dates = dv;
      }
      if (!dates) {
        for (var c = 0; c < row.length; c++) {
          var cv = String(row[c] || '').trim();
          if (dateListRe.test(cv)) { dates = cv; break; }
        }
      }
      if (!dates) continue;

      var status = statusCol >= 0 ? String(row[statusCol] || '').trim().toUpperCase() : '';
      var key = area + '|' + dates;
      if (status === 'ESCALATED_DL') result.escalation[key] = true;
      else                           result.companionship[key] = true;
    }
  } catch (e) {
    Logger.log('Agent3: Could not load MISSING_LOG — ' + e.message);
  }
  return result;
}

/**
 * Appends one row to MISSING_LOG, placing each value under its correct header by
 * NAME (not by position). This is what keeps dedup reliable: a positional append
 * silently corrupts dedup the moment someone reorders or inserts a column.
 * Creates a standard header row if the tab is empty.
 *
 * @param {Object} fields  map of header name -> value; unlisted columns left blank
 */
function a3_appendMissingLog(fields) {
  var sheet   = getTab('MISSING_LOG');
  var lastCol = sheet.getLastColumn();
  var headers = lastCol > 0
    ? sheet.getRange(1, 1, 1, lastCol).getValues()[0].map(function(h) { return String(h).trim(); })
    : [];

  if (headers.length === 0 || headers.join('') === '') {
    headers = ['Area', 'Message_ID', 'Notified_Timestamp', 'Email_Sent_To', 'Missing_Dates',
               'Days_Missed_Count', 'Alert_Sent_Timestamp', 'Alert_Recipients', 'Alert_Status'];
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }

  var row = headers.map(function(h) {
    return Object.prototype.hasOwnProperty.call(fields, h) ? fields[h] : '';
  });
  sheet.appendRow(row);
}

/**
 * Builds a lookup of district name (lowercase) -> District Leader email(s).
 * Reads the dedicated Is_DL=TRUE rows in MISSION_ORG. Skips blank / placeholder
 * addresses. Both companion email slots are included.
 *
 * A district can have Is_DL=TRUE on TWO different rows at once: the real
 * teaching-area row currently holding the calling (set fresh every transfer),
 * and a separate "District Leader - X" tracking row (manually maintained). The
 * real area's own flag is always transfer-fresh, so it takes priority; the
 * tracking row is only used as a fallback for districts where no real area
 * currently supplies an email.
 */
function a3_buildDistrictLeaderLookup(missionOrg) {
  var map      = {};
  var fallback = {};
  missionOrg.forEach(function(o) {
    if (String(o['Is_DL'] || '').toUpperCase() !== 'TRUE') return;
    var district = String(o['District'] || '').trim().toLowerCase();
    if (!district) return;
    var emails = [o['Companion1_Email'], o['Companion2_Email']].filter(function(e) {
      if (!e || !e.trim()) return false;
      var l = e.toLowerCase();
      return l.indexOf('notreadyyet') < 0 && l.indexOf('tbd@') < 0;
    });
    if (!emails.length) return;
    var joined = emails.join(',');
    if (a3_isLeadershipRow(o)) {
      if (!(district in fallback)) fallback[district] = joined;
    } else {
      map[district] = joined;
    }
  });
  Object.keys(fallback).forEach(function(d) {
    if (!(d in map)) map[d] = fallback[d];
  });
  return map;
}

/**
 * Builds the HTML body for a District Leader escalation email (Spanish).
 */
function a3_buildEscalationHtml(areaName, dateList, count, formLink) {
  var items = dateList.map(function(d) { return '<li>' + a3_formatReadableDate(d) + '</li>'; }).join('');
  return '<div style="font-family: Arial, sans-serif; max-width: 600px;">' +
    '<h2 style="color:#173A72;">Alerta: Informes Nocturnos Faltantes</h2>' +
    '<p>Hola,</p>' +
    '<p>El área <strong>' + a3_escapeHtmlMail(areaName) + '</strong> no ha enviado su informe nocturno en ' +
    count + ' fecha(s):</p>' +
    '<ul>' + items + '</ul>' +
    '<p>Por favor, comuníquese con esta compañía para ayudarles a ponerse al día.</p>' +
    '<p><a href="' + formLink + '" style="background:#173A72;color:#fff;padding:10px 20px;' +
    'text-decoration:none;border-radius:4px;">Enviar Informe Nocturno</a></p>' +
    '<p style="color:#999;font-size:12px;">PMG Compass — ' + getMissionName() + '</p></div>';
}

/**
 * Loads all active MISSED_DAYS messages from MESSAGE_BANK.
 * Returns an array of message objects keyed by MESSAGE_BANK column headers.
 */
function a3_loadMissedDayMessages() {
  var messages = [];
  try {
    var data = a3_getSheetData('MESSAGE_BANK');
    if (!data || data.length < 2) return messages;

    var headers   = data[0].map(function(h) { return String(h).trim(); });
    var catIdx    = headers.indexOf('Category');
    var activeIdx = headers.indexOf('Active');

    for (var i = 1; i < data.length; i++) {
      var row      = data[i];
      var category = String(row[catIdx]    || '').trim().toUpperCase();
      var active   = String(row[activeIdx] || '').trim().toUpperCase();

      if (category === 'MISSED_DAYS' && active === 'TRUE') {
        var msg = {};
        headers.forEach(function(h, idx) { msg[h] = String(row[idx] || '').trim(); });
        messages.push(msg);
      }
    }
  } catch (e) {
    Logger.log('Agent3: Could not load MESSAGE_BANK — ' + e.message);
  }
  return messages;
}

/**
 * Returns a sorted array of YYYY-MM-DD strings with no submission for the given area,
 * looking back from yesterday up to `lookbackDays` days.
 *
 * Stops at yesterday — today's submission is not due yet at 6 AM.
 */
function a3_getMissingDates(areaName, submittedDates, today, lookbackDays, transferStartStr) {
  var areaDates = submittedDates[areaName] || {};
  var missing   = [];

  // Never flag days before the system went live, OR before the current transfer
  // started — whichever is LATER. Use a3_toDateString to normalize first —
  // AGENT_CONFIG date cells return a Date object from getValues(), not a string.
  var systemStartStr = getConfig('SYSTEM_START_DATE');
  var hardFloor = null;
  [systemStartStr, transferStartStr].forEach(function(raw) {
    if (!raw) return;
    var normalized = a3_toDateString(raw);
    if (!normalized) return;
    var parsed = a3_parseLocalDate(normalized);
    if (parsed && (!hardFloor || parsed > hardFloor)) hardFloor = parsed;
  });

  for (var d = 1; d <= lookbackDays; d++) {
    var checkDate = new Date(today.getFullYear(), today.getMonth(), today.getDate() - d);
    if (hardFloor && checkDate < hardFloor) break;  // don't go before system launch or this transfer's start
    var dateStr = a3_toDateString(checkDate);
    if (dateStr && !areaDates[dateStr]) missing.push(dateStr);
  }

  return missing.sort();  // chronological — oldest missing date first
}

/**
 * Takes a sorted array of YYYY-MM-DD strings and returns only the consecutive runs
 * that are 2 or more days long.
 *
 * Example:
 *   ['2026-05-20','2026-05-21','2026-05-23'] -> [['2026-05-20','2026-05-21']]
 *   May 23 is isolated (gap of 1 day), so it is excluded.
 */
function a3_findConsecutiveGaps(sortedMissingDates) {
  if (sortedMissingDates.length === 0) return [];

  var gaps       = [];
  var currentRun = [sortedMissingDates[0]];

  for (var i = 1; i < sortedMissingDates.length; i++) {
    var prev    = a3_parseLocalDate(sortedMissingDates[i - 1]);
    var curr    = a3_parseLocalDate(sortedMissingDates[i]);
    var dayDiff = Math.round((curr - prev) / 86400000);

    if (dayDiff === 1) {
      currentRun.push(sortedMissingDates[i]);
    } else {
      if (currentRun.length >= 2) gaps.push(currentRun);
      currentRun = [sortedMissingDates[i]];
    }
  }

  if (currentRun.length >= 2) gaps.push(currentRun);
  return gaps;
}

// ─── SHARED UTILITIES ───────────────────────────────────────────────────────

/**
 * Maps a renamed *_Attempt metric key to a legacy DAILY_LOG header, mirroring
 * the Provo original's migration-alias mechanism. No CCSM metric key
 * currently needs an alias; kept as a documented no-op hook so future header
 * renames can add one without restructuring a3_buildLiveSnapshot.
 */
function a3_legacyMetricAlias(key) {
  var aliases = {};
  return aliases[key] || key;
}

/**
 * Returns true if a MISSION_ORG row is a leadership role (not a submitting area).
 * Leadership rows exist for email routing only — they never submit the nightly form.
 *
 * IMPORTANT: this must key off Area_Name, not the Is_ZL/Is_STL/Is_DL/Is_AP/
 * Is_MP flags. A REAL teaching-area row can legitimately have one of those
 * flags set TRUE too — whenever that area's companion currently holds a
 * leadership calling — which would wrongly exclude it from missed-day
 * checks entirely. IMOS role titles (Mission President, Zone Leader,
 * District Leader, etc.) are standard English across all missions
 * regardless of the mission's working language, so this pattern is
 * unchanged from the Provo original.
 */
function a3_isLeadershipRow(areaObj) {
  var name = (areaObj['Area_Name'] || '').trim();
  return /^(Mission President|Assistant to President|Zone Leader|Sister Training Leader -|District Leader -)/i.test(name);
}

/**
 * Converts a Date object, Google Sheets serial number, or date string to 'YYYY-MM-DD'.
 * Returns null if conversion fails.
 *
 * Serial number note: Sheets stores dates as days since Dec 30, 1899.
 * We re-format using the mission's configured timezone so the date matches
 * what the user sees in the sheet.
 */
function a3_toDateString(val) {
  if (val === null || val === undefined || val === '') return null;

  var d;
  if (val instanceof Date) {
    d = val;
  } else if (typeof val === 'number') {
    d = new Date(Date.UTC(1899, 11, 30) + val * 86400000);
  } else {
    var s = String(val).trim();
    // yyyy-MM-dd strings must be taken literally — new Date('yyyy-MM-dd')
    // parses as UTC midnight, which is the PREVIOUS day in Santiago time.
    var m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return m[1] + '-' + m[2] + '-' + m[3];
    d = new Date(s);
  }

  if (isNaN(d.getTime())) return null;
  return Utilities.formatDate(d, getMissionTimezone(), 'yyyy-MM-dd');
}

/**
 * Parses a 'YYYY-MM-DD' string into a local Date at midnight.
 * Safer than new Date('YYYY-MM-DD') which shifts by timezone offset in V8.
 */
function a3_parseLocalDate(dateStr) {
  var p = dateStr.split('-');
  return new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
}

/**
 * Formats a YYYY-MM-DD string as a human-readable date like "Monday, May 25".
 * Uses noon to avoid DST boundary edge cases shifting the date by one day.
 */
function a3_formatReadableDate(dateStr) {
  var d = new Date(dateStr + 'T12:00:00');
  return Utilities.formatDate(d, getMissionTimezone(), 'EEEE, MMMM d');
}

/**
 * Replaces placeholder variables in a message subject or body template.
 * Supported placeholders: {{AREA}}, {{MISSING_DATES}}, {{FORM_LINK}}
 */
function a3_injectVars(text, areaName, dateList, formLink) {
  return (text || '')
    .replace(/\{\{AREA\}\}/g,          areaName)
    .replace(/\{\{MISSING_DATES\}\}/g, dateList)
    .replace(/\{\{FORM_LINK\}\}/g,     formLink || '[FORM LINK NOT SET IN AGENT_CONFIG]');
}

/**
 * Wraps the plain-text MESSAGE_BANK missed-days prose in a polished HTML
 * shell so the alert renders as a formatted email instead of one flat
 * paragraph.
 *
 * The bare form URL embedded in the prose is lifted out and rendered as a
 * styled "Enviar Informe Nocturno" button; whatever colon/punctuation
 * preceded it is tidied so the sentence still reads cleanly.
 *
 * @param {string} bodyText  fully injected prose (area/dates/link already filled)
 * @param {string} formLink  nightly form URL (used for the button)
 * @returns {string} HTML email body
 */
function a3_buildMissedDaysHtml(bodyText, formLink) {
  var text   = String(bodyText || '').trim();
  var btnUrl = (formLink && formLink.indexOf('http') === 0) ? formLink : '';

  // Lift any bare URL out of the sentence (with an optional preceding colon) and
  // replace it with a period so the prose reads naturally without the raw link.
  text = text.replace(/\s*:?\s*https?:\/\/[^\s]+/g, function(m) {
    if (!btnUrl) btnUrl = m.match(/https?:\/\/[^\s]+/)[0].replace(/[.,;:)]+$/, '');
    return '.';
  });

  // Tidy artifacts left by the URL removal: " ." -> ".", repeated "." and spaces.
  text = text.replace(/\s+\./g, '.').replace(/\.{2,}/g, '.').replace(/\s{2,}/g, ' ').trim();

  // Split into paragraphs on blank lines; fall back to the whole block.
  var paras = text.split(/\n{2,}/).map(function(p) { return p.trim(); }).filter(Boolean);
  if (paras.length === 0) paras = [text];

  var lines = [];
  lines.push('<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:640px;margin:0 auto;line-height:1.55;">');
  lines.push('<h2 style="color:#1a4d7c;margin:0 0 16px 0;">Recordatorio de Informe Nocturno</h2>');
  paras.forEach(function(p) {
    lines.push('<p style="margin:0 0 14px 0;">' + a3_escapeHtmlMail(p).replace(/\n/g, '<br>') + '</p>');
  });
  if (btnUrl) {
    lines.push('<p style="margin:22px 0;"><a href="' + a3_escapeHtmlMail(btnUrl) + '" ' +
      'style="background:#1a4d7c;color:#fff;padding:11px 22px;text-decoration:none;' +
      'border-radius:4px;font-weight:bold;display:inline-block;">Enviar Informe Nocturno</a></p>');
  }
  lines.push('<p style="color:#6b7280;font-size:12px;margin-top:24px;">— PMG Compass (' + getMissionName() + ')</p>');
  lines.push('</body></html>');
  return lines.join('\n');
}

/**
 * Escapes HTML special characters for safe inclusion in email bodies.
 */
function a3_escapeHtmlMail(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── SECOND DAILY TRIGGER (EVENING CHECK) ──────────────────────────────────

function setupAgent3EveningTrigger() {
  deleteTriggerByName('runAgent3Evening');
  ScriptApp.newTrigger('runAgent3Evening')
    .timeBased()
    .everyDays(1)
    .atHour(21)
    .create();
  Logger.log('Agent3 evening trigger created: daily at 9 PM');
}

function runAgent3Evening() {
  runAgent3();
}
