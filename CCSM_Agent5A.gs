/**
 * ============================================================
 * CCSM_Agent5A.gs — Dashboard Summary + Weekly KI Agent
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of Agent5A.gs (docs/Agent5A.gs in PMG-Compass) for the CCSM Spanish
 * form set. Internal a5a_* function names are kept identical to the Provo
 * original so future diffs stay readable; the form column constants, the
 * effort breakdown (Todo/La mayor parte/Algo via ccsmEffortScore()), and the
 * timezone source are changed to Spanish/CCSM equivalents.
 *
 * STRUCTURAL CHANGE vs Provo: WEEKLY_KI is no longer derived from DAILY_LOG.
 * CCSM's weekly form captures each area's own SELF-REPORTED results (Real)
 * and goals (Meta) for 7 key indicators directly — those are absolute
 * values, not daily increments, so a5a_writeWeeklyKI is replaced wholesale
 * with a parser over WEEKLY_FORM_RAW instead of an aggregator over DAILY_LOG.
 *
 * SCHEDULE: Every day at noon
 *           Run setupAgent5ATrigger() ONCE to create the trigger.
 *
 * WHAT IT DOES:
 *   1. Reads LIVE_SNAPSHOT, DAILY_LOG, NIGHTLY_FORM_RAW, WEEKLY_FORM_RAW,
 *      MISSION_ORG, GOALS_CONFIG
 *   2. Computes mission-wide and zone-level metric totals (4 windows each)
 *   3. Computes per-area submission compliance for the current week
 *   4. Computes effort breakdown (Todo/La mayor parte/Algo) from
 *      NIGHTLY_FORM_RAW for the last 7 days
 *   5. Overwrites DASHBOARD_SUMMARY with all computed data
 *   6. Rebuilds WEEKLY_KI by parsing WEEKLY_FORM_RAW's Real/Meta columns
 *      (one row per area per week-end; duplicate submissions for the same
 *      area+week keep the LATEST by form timestamp — not summed)
 *   7. Logs the run to AGENT_RUN_LOG
 *
 * NO GEMINI, NO EMAIL.
 *
 * ── DASHBOARD_SUMMARY SCHEMA ─────────────────────────────────────────────
 * All rows share one header row. The record_type column identifies the section.
 * Streamlit reads the whole tab and filters by record_type.
 *
 *   Columns:
 *   record_type | metric_key | metric_name | zone | area | district
 *     | val_7d | val_14d | val_28d | val_transfer | goal_weekly
 *     | date | all_count | most_count | some_count
 *     | submitted_count | total_areas | meta_key | meta_value
 *
 *   record_type='META'       — meta_key / meta_value pairs (timestamp, dates, counts)
 *   record_type='MISSION'    — mission totals per metric; uses val_* + goal_weekly
 *   record_type='ZONE'       — zone totals per metric; uses zone + val_*
 *   record_type='COMPLIANCE' — per-area: area, zone, district, submitted_count, date
 *   record_type='EFFORT'     — daily effort: date, all_count, most_count, some_count, total_areas
 *
 * ── WEEKLY_KI SCHEMA ──────────────────────────────────────────────────────
 *   Week_End_Date | Area | Zone | District |
 *     ki_new_people_real | ki_new_people_meta |
 *     ki_member_lessons_real | ki_member_lessons_meta |
 *     ki_friends_sacrament_real | ki_friends_sacrament_meta |
 *     ki_friends_first_week_real | ki_friends_first_week_meta |
 *     ki_baptismal_date_real | ki_baptismal_date_meta |
 *     ki_baptized_confirmed_real | ki_baptized_confirmed_meta |
 *     ki_rc_at_church_real | ki_rc_at_church_meta |
 *     leader_call | correlation_meeting
 *   One row per area per week-end (Sunday). Rebuilt completely on each run.
 */

// ─── CONSTANTS ───────────────────────────────────────────────────────────────

// Column header for the effort question in NIGHTLY_FORM_RAW.
// Must match CCSM_NIGHTLY_QUESTIONS 'effort' headerEs in CcsmData.gs / the
// exact question text in the live CCSM Spanish Google Form.
var A5A_EFFORT_COL = '¿Dio todo, la mayor parte o algo de esfuerzo en el altar del sacrificio hoy?';

// ─── MAIN ENTRY POINT ────────────────────────────────────────────────────────

/**
 * Called by the daily noon time trigger.
 * Loads all source data, computes summaries, writes DASHBOARD_SUMMARY and WEEKLY_KI.
 */
function runAgent5A() {
  var status = 'SUCCESS';
  var notes  = [];

  try {
    Logger.log('Agent5A: Starting dashboard summary — ' + new Date().toISOString());

    // Load reference data
    var missionOrg  = a5a_loadMissionOrg();       // real submitting areas only
    var metrics     = a5a_loadMetrics();           // active NIGHTLY metrics
    var goals       = a5a_loadGoals(metrics);      // {area: {metric_key: weekly_goal}}
    var liveSnap    = a5a_loadLiveSnapshot(metrics); // {area: {key_7d: v, key_14d: v, ...}}
    var dailyLog    = a5a_loadDailyLog(metrics);   // array of {date, area, zone, district, totals}
    var nightlyRaw  = a5a_getSheetData('NIGHTLY_FORM_RAW');
    var weeklyRaw   = a5a_getSheetData('WEEKLY_FORM_RAW');

    var transferStart = getConfig('TRANSFER_START_DATE') || '';

    // Compute aggregates
    var missionTotals = a5a_getMissionTotals(liveSnap, metrics, missionOrg);
    var zoneTotals    = a5a_getZoneTotals(liveSnap, metrics, missionOrg);
    var missionGoals  = a5a_getMissionGoals(goals, metrics, missionOrg);
    var compliance    = a5a_getComplianceData(dailyLog, missionOrg);
    var effort        = a5a_getEffortBreakdown(nightlyRaw);

    // Write output tabs
    var summaryRows = a5a_writeDashboardSummary(
      missionOrg, metrics, missionTotals, zoneTotals, missionGoals,
      goals, liveSnap, compliance, effort, transferStart
    );
    notes.push('DASHBOARD_SUMMARY: ' + summaryRows + ' rows written');

    var kiRows = a5a_writeWeeklyKI(missionOrg, weeklyRaw);
    notes.push('WEEKLY_KI: ' + kiRows + ' rows written');

    Logger.log('Agent5A: Complete — ' + notes.join(' | '));

  } catch (e) {
    status = 'ERROR';
    notes.push('ERROR: ' + e.message);
    Logger.log('Agent5A FATAL: ' + e.message + '\n' + (e.stack || ''));
  }

  // logRun(agent, status, recordsProcessed, emailsSent, durationMs, notes, error)
  logRun('Agent5A', status, null, null, null, notes.join(' | '));
}

// ─── TRIGGER SETUP ───────────────────────────────────────────────────────────

/**
 * Creates the daily noon trigger for Agent5A.
 * Run ONCE: Apps Script editor -> Run -> setupAgent5ATrigger
 * Safe to re-run — deletes any existing Agent5A trigger first.
 */
function setupAgent5ATrigger() {
  deleteTriggerByName('runAgent5A');
  ScriptApp.newTrigger('runAgent5A')
    .timeBased()
    .everyDays(1)
    .atHour(12)
    .create();
  Logger.log('Agent5A trigger created: runAgent5A daily at noon');
}

// ─── SHEET DATA HELPER ───────────────────────────────────────────────────────

/**
 * Returns all rows including the header as row [0].
 * Returns [] for missing or empty tabs rather than throwing.
 */
function a5a_getSheetData(tabName) {
  var sheet = getTab(tabName);
  if (!sheet || sheet.getLastRow() === 0) return [];
  return sheet.getDataRange().getValues();
}

// ─── DATA LOADERS ─────────────────────────────────────────────────────────────

/**
 * Loads active submitting areas from MISSION_ORG (excludes all leadership rows).
 * Returns array of objects keyed by column header.
 */
function a5a_loadMissionOrg() {
  var data = a5a_getSheetData('MISSION_ORG');
  if (!data || data.length < 2) throw new Error('MISSION_ORG is empty or missing headers');

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var areas   = [];

  for (var i = 1; i < data.length; i++) {
    var obj = {};
    headers.forEach(function(h, idx) {
      obj[h] = (data[i][idx] != null) ? String(data[i][idx]).trim() : '';
    });
    var isActive = obj['Active'] && obj['Active'].toUpperCase() === 'TRUE';
    if (!isActive || !obj['Area_Name']) continue;
    if (a5a_isLeadershipRow(obj)) continue;
    areas.push(obj);
  }

  return areas;
}

/**
 * Loads active NIGHTLY metrics from QUESTIONS_CONFIG.
 * Returns objects with at least: Metric_Key, Metric_Display_Name, Form_Column_Header.
 */
function a5a_loadMetrics() {
  var data = a5a_getSheetData('QUESTIONS_CONFIG');
  if (!data || data.length < 2) throw new Error('QUESTIONS_CONFIG is empty');

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var metrics = [];

  for (var i = 1; i < data.length; i++) {
    var m = {};
    headers.forEach(function(h, idx) {
      m[h] = (data[i][idx] != null) ? String(data[i][idx]).trim() : '';
    });
    var isActive   = m['Active'] && m['Active'].toUpperCase() === 'TRUE';
    var formType   = (m['Form_Type'] || '').toUpperCase();
    var isNightly  = (formType === 'NIGHTLY' || formType === '');
    if (isActive && isNightly && m['Metric_Key']) metrics.push(m);
  }

  return metrics;
}

/**
 * Loads weekly goals from GOALS_CONFIG.
 * Returns a nested map: { area_name: { metric_key: weekly_goal_number } }
 * Missing goals default to 0. Column headers in GOALS_CONFIG must match Metric_Keys.
 */
function a5a_loadGoals(metrics) {
  var data = a5a_getSheetData('GOALS_CONFIG');
  var goals = {};
  if (!data || data.length < 2) return goals;

  var headers    = data[0].map(function(h) { return String(h).trim(); });
  var areaIdx    = headers.indexOf('Area');
  if (areaIdx < 0) return goals;

  // Map metric keys to their column index in GOALS_CONFIG
  var metricColIdx = {};
  metrics.forEach(function(m) {
    var idx = headers.indexOf(m['Metric_Key']);
    if (idx >= 0) metricColIdx[m['Metric_Key']] = idx;
  });

  for (var i = 1; i < data.length; i++) {
    var area = String(data[i][areaIdx] || '').trim();
    if (!area) continue;
    goals[area] = {};
    metrics.forEach(function(m) {
      var key = m['Metric_Key'];
      var idx = metricColIdx[key];
      goals[area][key] = idx !== undefined ? (parseFloat(data[i][idx]) || 0) : 0;
    });
  }

  return goals;
}

/**
 * Loads LIVE_SNAPSHOT into a nested map:
 * { area_name: { 'metric_7d': value, 'metric_14d': value, ... } }
 */
function a5a_loadLiveSnapshot(metrics) {
  var data = a5a_getSheetData('LIVE_SNAPSHOT');
  var snap = {};
  if (!data || data.length < 2) return snap;

  // The real header row may not be row 1 — a stale legacy header ("Area_ID",
  // "Area_Name", ...) can sit above the agent-written header. Find the first
  // row whose first cell is exactly 'Area' and treat it as the header;
  // otherwise indexOf('Area') fails and every dashboard total computes as 0.
  var headerRowIdx = -1;
  for (var h = 0; h < Math.min(data.length, 5); h++) {
    if (String(data[h][0]).trim() === 'Area') { headerRowIdx = h; break; }
  }
  if (headerRowIdx < 0) return snap;

  var headers = data[headerRowIdx].map(function(hd) { return String(hd).trim(); });
  var areaIdx = headers.indexOf('Area');

  for (var i = headerRowIdx + 1; i < data.length; i++) {
    var area = String(data[i][areaIdx] || '').trim();
    if (!area) continue;
    snap[area] = {};
    headers.forEach(function(hd, idx) {
      snap[area][hd] = parseFloat(data[i][idx]) || 0;
    });
  }

  return snap;
}

/**
 * Loads DAILY_LOG into an array of row objects.
 * Each object: { date, area, zone, district, totals: {metric_key: value} }
 */
function a5a_loadDailyLog(metrics) {
  var data = a5a_getSheetData('DAILY_LOG');
  var rows = [];
  if (!data || data.length < 2) return rows;

  var headers  = data[0].map(function(h) { return String(h).trim(); });
  var areaIdx  = headers.indexOf('Area');
  var dateIdx  = headers.indexOf('Date');
  var zoneIdx  = headers.indexOf('Zone');
  var distIdx  = headers.indexOf('District');
  if (areaIdx < 0 || dateIdx < 0) return rows;

  // Mirrors Agent3's fallback-alias mechanism for legacy header renames. No
  // CCSM metric key currently needs an alias (kept as a documented no-op
  // hook, same as a3_legacyMetricAlias).
  var metricIdx = {};
  metrics.forEach(function(m) {
    var key = m['Metric_Key'];
    var idx = headers.indexOf(key);
    if (idx < 0) idx = headers.indexOf(a5a_legacyMetricAlias(key));
    if (idx >= 0) metricIdx[key] = idx;
  });

  for (var i = 1; i < data.length; i++) {
    var area    = String(data[i][areaIdx] || '').trim();
    var dateStr = a5a_toDateString(data[i][dateIdx]);
    if (!area || !dateStr) continue;

    var totals = {};
    metrics.forEach(function(m) {
      var idx = metricIdx[m['Metric_Key']];
      totals[m['Metric_Key']] = idx !== undefined ? (parseFloat(data[i][idx]) || 0) : 0;
    });

    rows.push({
      date:     dateStr,
      area:     area,
      zone:     zoneIdx >= 0 ? String(data[i][zoneIdx] || '').trim() : '',
      district: distIdx >= 0 ? String(data[i][distIdx] || '').trim() : '',
      totals:   totals
    });
  }

  return rows;
}

// ─── AGGREGATIONS ─────────────────────────────────────────────────────────────

/**
 * Sums LIVE_SNAPSHOT values across all active submitting areas to get mission totals.
 * Returns: { metric_key: { '7d': n, '14d': n, '28d': n, 'transfer': n } }
 */
function a5a_getMissionTotals(liveSnap, metrics, missionOrg) {
  var totals = {};
  metrics.forEach(function(m) {
    totals[m['Metric_Key']] = { '7d': 0, '14d': 0, '28d': 0, 'transfer': 0 };
  });

  missionOrg.forEach(function(areaObj) {
    var areaName = areaObj['Area_Name'];
    var snap     = liveSnap[areaName];
    if (!snap) return;

    metrics.forEach(function(m) {
      var key = m['Metric_Key'];
      totals[key]['7d']       += snap[key + '_7d']       || 0;
      totals[key]['14d']      += snap[key + '_14d']      || 0;
      totals[key]['28d']      += snap[key + '_28d']      || 0;
      totals[key]['transfer'] += snap[key + '_transfer'] || 0;
    });
  });

  return totals;
}

/**
 * Aggregates LIVE_SNAPSHOT values by zone.
 * Returns: { zone_name: { metric_key: { '7d': n, '14d': n, '28d': n, 'transfer': n } } }
 * Pre-initializes all zones from missionOrg so zone rows always appear even when
 * liveSnap has no matching entry for an area (e.g., before any data is submitted).
 */
function a5a_getZoneTotals(liveSnap, metrics, missionOrg) {
  var zones = {};

  // Pre-initialize every zone with zero totals so the output is always complete
  missionOrg.forEach(function(areaObj) {
    var zone = areaObj['Zone'] || '';
    if (!zone || zones[zone]) return;
    zones[zone] = {};
    metrics.forEach(function(m) {
      zones[zone][m['Metric_Key']] = { '7d': 0, '14d': 0, '28d': 0, 'transfer': 0 };
    });
  });

  // Add liveSnap values where available
  missionOrg.forEach(function(areaObj) {
    var areaName = areaObj['Area_Name'];
    var zone     = areaObj['Zone'] || '';
    var snap     = liveSnap[areaName];
    if (!zone || !snap) return;

    metrics.forEach(function(m) {
      var key = m['Metric_Key'];
      zones[zone][key]['7d']       += snap[key + '_7d']       || 0;
      zones[zone][key]['14d']      += snap[key + '_14d']      || 0;
      zones[zone][key]['28d']      += snap[key + '_28d']      || 0;
      zones[zone][key]['transfer'] += snap[key + '_transfer'] || 0;
    });
  });

  return zones;
}

/**
 * Sums per-area weekly goals across all areas to get mission-level weekly goals.
 * Returns: { metric_key: total_goal }
 */
function a5a_getMissionGoals(goals, metrics, missionOrg) {
  var missionGoals = {};
  metrics.forEach(function(m) { missionGoals[m['Metric_Key']] = 0; });

  missionOrg.forEach(function(areaObj) {
    var areaGoals = goals[areaObj['Area_Name']];
    if (!areaGoals) return;
    metrics.forEach(function(m) {
      missionGoals[m['Metric_Key']] += areaGoals[m['Metric_Key']] || 0;
    });
  });

  return missionGoals;
}

/**
 * Computes how many days each area has submitted in the current calendar week (Mon–today).
 * Returns array of { area, zone, district, submitted_count, last_submitted } objects.
 */
function a5a_getComplianceData(dailyLog, missionOrg) {
  var weekStart = a5a_getCurrentWeekStart();  // Monday YYYY-MM-DD

  // Build map: area -> { count, lastDate }
  var areaStats = {};
  dailyLog.forEach(function(row) {
    if (row.date < weekStart) return;  // before this week
    if (!areaStats[row.area]) areaStats[row.area] = { count: 0, lastDate: '' };
    areaStats[row.area].count++;
    if (row.date > areaStats[row.area].lastDate) areaStats[row.area].lastDate = row.date;
  });

  return missionOrg.map(function(areaObj) {
    var name  = areaObj['Area_Name'];
    var stats = areaStats[name] || { count: 0, lastDate: '' };
    return {
      area:      name,
      zone:      areaObj['Zone']     || '',
      district:  areaObj['District'] || '',
      submitted: stats.count,
      lastDate:  stats.lastDate
    };
  });
}

/**
 * Scans NIGHTLY_FORM_RAW for the last 7 days and counts Todo/La mayor
 * parte/Algo effort responses via ccsmEffortScore() (CCSM_Helpers.gs).
 * Handles the multi-section form structure — finds the effort column offset within each section.
 * Returns array of { date, all, most, some, total } objects sorted by date ascending.
 * (Field names all/most/some are kept from the Provo schema — they now hold
 * the Todo/La mayor parte/Algo counts respectively.)
 */
function a5a_getEffortBreakdown(nightlyRaw) {
  var result = {};
  if (!nightlyRaw || nightlyRaw.length < 2) return [];

  var headers    = nightlyRaw[0].map(function(h) { return String(h).trim(); });
  var areaTarget  = CCSM_FORM_STRUCTURAL.areaCol.toLowerCase();
  var dateTarget  = CCSM_FORM_STRUCTURAL.dateCol.toLowerCase();
  var effortTarget = A5A_EFFORT_COL.toLowerCase();

  // Find section structure: area column indices and date/effort offsets
  var areaCols = [];
  headers.forEach(function(h, idx) {
    if (h.toLowerCase() === areaTarget) areaCols.push(idx);
  });
  if (areaCols.length === 0) return [];

  // Build offset map from the first section
  var sectionStart = areaCols[0];
  var sectionEnd   = areaCols.length > 1 ? areaCols[1] : headers.length;
  var offsetMap    = {};
  for (var j = sectionStart; j < sectionEnd; j++) {
    var lh = headers[j].toLowerCase();
    if (!(lh in offsetMap)) offsetMap[lh] = j - sectionStart;
  }

  var dateOffset   = offsetMap[dateTarget];
  var effortOffset = offsetMap[effortTarget];
  if (dateOffset === undefined || effortOffset === undefined) return [];

  // Calculate lookback cutoff (7 days ago)
  var today    = new Date();
  today.setHours(0, 0, 0, 0);
  var cutoff   = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 7);
  var cutoffStr = a5a_toDateString(cutoff);

  for (var i = 1; i < nightlyRaw.length; i++) {
    var row = nightlyRaw[i];

    // Find the filled section
    var sectionIdx = -1;
    for (var s = 0; s < areaCols.length; s++) {
      if (String(row[areaCols[s]] || '').trim()) { sectionIdx = areaCols[s]; break; }
    }
    if (sectionIdx < 0) continue;

    var dateStr   = a5a_toDateString(row[sectionIdx + dateOffset]);
    var effortRaw = String(row[sectionIdx + effortOffset] || '').trim();
    if (!dateStr || dateStr < cutoffStr) continue;

    if (!result[dateStr]) result[dateStr] = { date: dateStr, all: 0, most: 0, some: 0, total: 0 };
    result[dateStr].total++;

    var score = ccsmEffortScore(effortRaw);
    if      (score === 3) result[dateStr].all++;   // Todo
    else if (score === 2) result[dateStr].most++;  // La mayor parte
    else if (score === 1) result[dateStr].some++;  // Algo
  }

  return Object.keys(result).sort().map(function(d) { return result[d]; });
}

// ─── DASHBOARD_SUMMARY WRITER ─────────────────────────────────────────────────

/**
 * Builds and writes all sections to DASHBOARD_SUMMARY.
 * Returns total data row count written (excludes header).
 *
 * All rows share this header:
 * record_type | metric_key | metric_name | zone | area | district
 *   | val_7d | val_14d | val_28d | val_transfer | goal_weekly
 *   | date | all_count | most_count | some_count
 *   | submitted_count | total_areas | meta_key | meta_value
 */
function a5a_writeDashboardSummary(
  missionOrg, metrics, missionTotals, zoneTotals, missionGoals,
  goals, liveSnap, compliance, effort, transferStart
) {
  var tz  = getMissionTimezone();
  var now = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd HH:mm');

  var header = [
    'record_type','metric_key','metric_name','zone','area','district',
    'val_7d','val_14d','val_28d','val_transfer','goal_weekly',
    'date','all_count','most_count','some_count',
    'submitted_count','total_areas','meta_key','meta_value'
  ];

  // Helper: empty row with record_type set
  function blankRow(type) {
    var r = header.map(function() { return ''; });
    r[0] = type;
    return r;
  }
  function col(name) { return header.indexOf(name); }

  var rows = [header];

  // ── META section ──────────────────────────────────────────────────────
  var weekStart    = a5a_getCurrentWeekStart();
  var weekEnd      = a5a_getWeekEnd(weekStart);
  var submittedToday = compliance.filter(function(c) {
    var today = a5a_toDateString(new Date());
    return c.lastDate === today;
  }).length;
  var submittedThisWeek = compliance.filter(function(c) { return c.submitted > 0; }).length;

  var metaRows = [
    ['generated_at',       now],
    ['current_week_start', weekStart],
    ['current_week_end',   weekEnd],
    ['transfer_start',     transferStart],
    ['total_areas',        String(missionOrg.length)],
    ['submitted_today',    String(submittedToday)],
    ['compliance_today',   missionOrg.length > 0 ? (submittedToday / missionOrg.length * 100).toFixed(1) : '0'],
    ['submitted_this_week', String(submittedThisWeek)],
    ['compliance_week',    missionOrg.length > 0 ? (submittedThisWeek / missionOrg.length * 100).toFixed(1) : '0']
  ];

  metaRows.forEach(function(pair) {
    var r = blankRow('META');
    r[col('meta_key')]   = pair[0];
    r[col('meta_value')] = pair[1];
    rows.push(r);
  });

  // ── MISSION section ───────────────────────────────────────────────────
  metrics.forEach(function(m) {
    var key    = m['Metric_Key'];
    var totals = missionTotals[key] || {};
    var r = blankRow('MISSION');
    r[col('metric_key')]    = key;
    r[col('metric_name')]   = m['Metric_Display_Name'] || key;
    r[col('val_7d')]        = totals['7d']       || 0;
    r[col('val_14d')]       = totals['14d']      || 0;
    r[col('val_28d')]       = totals['28d']      || 0;
    r[col('val_transfer')]  = totals['transfer'] || 0;
    r[col('goal_weekly')]   = missionGoals[key]  || 0;
    rows.push(r);
  });

  // ── ZONE section ──────────────────────────────────────────────────────
  Object.keys(zoneTotals).sort().forEach(function(zone) {
    var zoneData = zoneTotals[zone];
    metrics.forEach(function(m) {
      var key    = m['Metric_Key'];
      var totals = zoneData[key] || {};
      var r = blankRow('ZONE');
      r[col('zone')]         = zone;
      r[col('metric_key')]   = key;
      r[col('metric_name')]  = m['Metric_Display_Name'] || key;
      r[col('val_7d')]       = totals['7d']       || 0;
      r[col('val_14d')]      = totals['14d']      || 0;
      r[col('val_28d')]      = totals['28d']      || 0;
      r[col('val_transfer')] = totals['transfer'] || 0;
      rows.push(r);
    });
  });

  // ── COMPLIANCE section ────────────────────────────────────────────────
  compliance.forEach(function(c) {
    var r = blankRow('COMPLIANCE');
    r[col('area')]            = c.area;
    r[col('zone')]            = c.zone;
    r[col('district')]        = c.district;
    r[col('submitted_count')] = c.submitted;
    r[col('total_areas')]     = missionOrg.length;
    r[col('date')]            = c.lastDate;
    rows.push(r);
  });

  // ── EFFORT section ────────────────────────────────────────────────────
  effort.forEach(function(e) {
    var r = blankRow('EFFORT');
    r[col('date')]        = e.date;
    r[col('all_count')]   = e.all;
    r[col('most_count')]  = e.most;
    r[col('some_count')]  = e.some;
    r[col('total_areas')] = e.total;
    rows.push(r);
  });

  overwriteTab('DASHBOARD_SUMMARY', rows);
  return rows.length - 1;  // excludes header
}

// ─── WEEKLY_KI WRITER ──────────────────────────────────────────────────────

/**
 * Analyzes WEEKLY_FORM_RAW headers and returns the section structure.
 *
 * The weekly form is split into sections — one per zone, exactly like
 * NIGHTLY_FORM_RAW (see a3_parseSectionStructure in CCSM_Agent3.gs for the
 * general technique). Each section repeats: area, 3 intro questions (date,
 * leader call Sí/No, correlation meeting Sí/No), then all 7 "(Real)" key
 * indicator columns, then all 7 "(Meta)" key indicator columns — grouped by
 * Real/Meta, NOT interleaved per-indicator like the CCSM_WEEKLY_QUESTIONS
 * array (see that array's header comment in CcsmData.gs). Offsets are
 * learned by header TEXT within the first section, so the grouped-vs-
 * interleaved distinction never matters to this lookup.
 *
 * Returns { areaCols, zoneIdx, dateOffset, leaderCallOffset,
 *           correlationOffset, metricOffsets: {ki_key: offset} }.
 */
function a5a_normHeader(h) {
  return String(h).toLowerCase().replace(/['’]/g, '').replace(/\s+/g, ' ').trim();
}

function a5a_weeklyQuestionHeader_(key) {
  for (var i = 0; i < CCSM_WEEKLY_QUESTIONS.length; i++) {
    if (CCSM_WEEKLY_QUESTIONS[i].key === key) return CCSM_WEEKLY_QUESTIONS[i].headerEs;
  }
  return '';
}

function a5a_parseWeeklySectionStructure(headers, kiKeys) {
  var areaTarget = a5a_normHeader(CCSM_FORM_STRUCTURAL.areaCol);
  var zoneTarget = a5a_normHeader(CCSM_FORM_STRUCTURAL.zoneCol);
  var dateTarget = a5a_normHeader(CCSM_FORM_STRUCTURAL.dateCol);

  var areaCols = [];
  var zoneIdx  = -1;

  headers.forEach(function(h, idx) {
    var norm = a5a_normHeader(h);
    if (norm === areaTarget) areaCols.push(idx);
    if (norm === zoneTarget && zoneIdx < 0) zoneIdx = idx;
  });

  if (areaCols.length === 0) throw new Error(
    'WEEKLY_FORM_RAW: no column matching "' + CCSM_FORM_STRUCTURAL.areaCol + '" found.'
  );

  // Use the first section as the template to learn column offsets
  var sectionStart = areaCols[0];
  var sectionEnd   = areaCols.length > 1 ? areaCols[1] : headers.length;

  var offsetByHeader = {};
  for (var i = sectionStart; i < sectionEnd; i++) {
    var h = a5a_normHeader(headers[i]);
    if (!(h in offsetByHeader)) offsetByHeader[h] = i - sectionStart;
  }

  var dateOffset = offsetByHeader[dateTarget];
  if (dateOffset === undefined) throw new Error(
    'WEEKLY_FORM_RAW: cannot find "' + CCSM_FORM_STRUCTURAL.dateCol + '" within a section.'
  );

  var leaderCallOffset  = offsetByHeader[a5a_normHeader(a5a_weeklyQuestionHeader_('leader_call'))];
  var correlationOffset = offsetByHeader[a5a_normHeader(a5a_weeklyQuestionHeader_('correlation_meeting'))];

  var metricOffsets = {};
  kiKeys.forEach(function(key) {
    var headerEs = a5a_weeklyQuestionHeader_(key);
    var offset   = offsetByHeader[a5a_normHeader(headerEs)];
    if (offset !== undefined) {
      metricOffsets[key] = offset;
    } else {
      Logger.log('Agent5A WARNING: "' + headerEs + '" not found in a WEEKLY_FORM_RAW section — check CCSM_WEEKLY_QUESTIONS.');
    }
  });

  return {
    areaCols: areaCols, zoneIdx: zoneIdx, dateOffset: dateOffset,
    leaderCallOffset: leaderCallOffset, correlationOffset: correlationOffset,
    metricOffsets: metricOffsets
  };
}

/**
 * Rebuilds WEEKLY_KI by parsing WEEKLY_FORM_RAW's self-reported Real/Meta
 * key-indicator columns directly — NOT derived from DAILY_LOG. CCSM's
 * weekly form separately captures each area's own reported RESULTS (Real)
 * and GOALS (Meta) for the week; these are absolute values, so summing
 * daily activity (the Provo approach) would not reproduce them.
 *
 * Bucketing: each row's self-reported date (report_date) is mapped to its
 * Sunday week-end via a5a_getWeekEnd(). One row per area per week-end. If
 * an area submits more than once for the same week-end, the LATEST
 * submission BY FORM TIMESTAMP (column A, "Marca temporal") wins — Real/
 * Meta values are absolute results/goals, not increments, so they must
 * never be summed or OR'd the way Agent3 combines same-day daily metrics.
 *
 * 'Sí'/'No' -> 'TRUE'/'FALSE' for leader_call and correlation_meeting.
 *
 * Returns total data row count written (excludes header).
 */
function a5a_writeWeeklyKI(missionOrg, weeklyRaw) {
  var kiKeys = CCSM_WEEKLY_QUESTIONS.filter(function(q) {
    return q.key.indexOf('ki_') === 0;
  }).map(function(q) { return q.key; });

  var headerRow = ['Week_End_Date', 'Area', 'Zone', 'District']
    .concat(kiKeys)
    .concat(['leader_call', 'correlation_meeting']);

  if (!weeklyRaw || weeklyRaw.length < 2) {
    overwriteTab('WEEKLY_KI', [headerRow]);
    return 0;
  }

  // Canonical area name lookup + district map, mirroring Agent3's
  // a3_buildAreaLookup — normalizes free-text area names typed on the form.
  var areaLookup  = {};
  var districtMap = {};
  missionOrg.forEach(function(a) {
    if (a['Area_Name']) {
      areaLookup[a['Area_Name'].toLowerCase()] = a['Area_Name'];
      districtMap[a['Area_Name']] = a['District'] || '';
    }
  });

  var headers     = weeklyRaw[0].map(function(h) { return String(h).trim(); });
  var sectionInfo = a5a_parseWeeklySectionStructure(headers, kiKeys);

  // Aggregate: key = "area|week_end" -> latest-winning entry
  var agg = {};

  for (var i = 1; i < weeklyRaw.length; i++) {
    var row = weeklyRaw[i];

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
      Logger.log('Agent5A: Unrecognized area "' + rawArea + '" in WEEKLY_FORM_RAW row ' + (i + 1) + ' — skipped');
      continue;
    }

    var rawDate = row[sectionStart + sectionInfo.dateOffset];
    var dateStr = a5a_toDateString(rawDate);
    if (!dateStr) {
      Logger.log('Agent5A: Invalid date in WEEKLY_FORM_RAW row ' + (i + 1) + ' for "' + rawArea + '" — skipped');
      continue;
    }

    var weekEnd = a5a_getWeekEnd(dateStr);
    var key     = canonArea + '|' + weekEnd;

    var tsCell = row[0];
    var ts = tsCell instanceof Date ? tsCell.getTime() : (Date.parse(tsCell) || 0);

    // Keep only the latest submission by form timestamp for this area+week.
    if (agg[key] && agg[key].ts >= ts) continue;

    var rawZone = sectionInfo.zoneIdx >= 0 ? String(row[sectionInfo.zoneIdx] || '').trim() : '';

    var values = {};
    kiKeys.forEach(function(k) {
      var offset = sectionInfo.metricOffsets[k];
      values[k] = offset !== undefined ? (parseFloat(row[sectionStart + offset]) || 0) : 0;
    });

    var leaderRaw = sectionInfo.leaderCallOffset !== undefined
      ? String(row[sectionStart + sectionInfo.leaderCallOffset] || '').trim() : '';
    var corrRaw = sectionInfo.correlationOffset !== undefined
      ? String(row[sectionStart + sectionInfo.correlationOffset] || '').trim() : '';

    agg[key] = {
      ts:                  ts,
      area:                canonArea,
      zone:                rawZone,
      district:            districtMap[canonArea] || '',
      week_end:            weekEnd,
      values:              values,
      leader_call:         leaderRaw === 'Sí' ? 'TRUE' : 'FALSE',
      correlation_meeting: corrRaw   === 'Sí' ? 'TRUE' : 'FALSE'
    };
  }

  // Build output rows — sort by week_end desc, then area asc
  var outputRows = [headerRow];
  Object.keys(agg).sort(function(a, b) {
    var wa = agg[a].week_end, wb = agg[b].week_end;
    if (wb !== wa) return wb > wa ? 1 : -1;
    return agg[a].area.localeCompare(agg[b].area);
  }).forEach(function(key) {
    var entry = agg[key];
    var row   = [entry.week_end, entry.area, entry.zone, entry.district];
    kiKeys.forEach(function(k) { row.push(entry.values[k]); });
    row.push(entry.leader_call, entry.correlation_meeting);
    outputRows.push(row);
  });

  overwriteTab('WEEKLY_KI', outputRows);
  return outputRows.length - 1;
}

// ─── DATE UTILITIES ────────────────────────────────────────────────────────

/**
 * Converts a Date object, Sheets serial number, or date string to 'YYYY-MM-DD'.
 * Returns null if conversion fails.
 */
function a5a_toDateString(val) {
  if (val === null || val === undefined || val === '') return null;
  var d;
  if (val instanceof Date) {
    d = val;
  } else if (typeof val === 'number') {
    d = new Date(Date.UTC(1899, 11, 30) + val * 86400000);
  } else {
    var s = String(val).trim();
    // yyyy-MM-dd strings must be taken literally — new Date('yyyy-MM-dd')
    // parses as UTC midnight, i.e. the PREVIOUS day in Santiago time.
    var m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return m[1] + '-' + m[2] + '-' + m[3];
    d = new Date(s);
  }
  if (isNaN(d.getTime())) return null;
  return Utilities.formatDate(d, getMissionTimezone(), 'yyyy-MM-dd');
}

/**
 * Maps a renamed metric key to its legacy DAILY_LOG header, mirroring
 * Agent3's migration-alias mechanism. No CCSM metric key currently needs an
 * alias; kept as a documented no-op hook so future header renames can add
 * one without restructuring a5a_loadDailyLog.
 */
function a5a_legacyMetricAlias(key) {
  var aliases = {};
  return aliases[key] || key;
}

/**
 * Parses 'YYYY-MM-DD' string into a local Date at midnight.
 */
function a5a_parseLocalDate(dateStr) {
  var p = dateStr.split('-');
  return new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
}

/**
 * Returns the Sunday (week-end) date for the week that contains the given YYYY-MM-DD date.
 * Week runs Monday–Sunday. If date is a Sunday, returns that same date.
 */
function a5a_getWeekEnd(dateStr) {
  var d   = a5a_parseLocalDate(dateStr);
  var day = d.getDay();  // 0=Sun, 1=Mon, ..., 6=Sat
  var daysToSunday = day === 0 ? 0 : 7 - day;
  var sunday = new Date(d.getFullYear(), d.getMonth(), d.getDate() + daysToSunday);
  return a5a_toDateString(sunday);
}

/**
 * Returns the Monday of the current calendar week as 'YYYY-MM-DD'.
 */
function a5a_getCurrentWeekStart() {
  var today = new Date();
  today.setHours(0, 0, 0, 0);
  var day  = today.getDay();  // 0=Sun
  var diff = day === 0 ? -6 : 1 - day;  // roll back to Monday
  var monday = new Date(today.getFullYear(), today.getMonth(), today.getDate() + diff);
  return a5a_toDateString(monday);
}

/**
 * Returns true if a MISSION_ORG row is a leadership/senior tracking row
 * (not a submitting area).
 * Keyed off Area_Name — NOT the Is_ZL/Is_STL/Is_DL/Is_AP/Is_MP flags, which
 * are legitimately TRUE on real teaching areas whose companionship holds the
 * calling. Mirrors a3_isLeadershipRow. IMOS role titles (Mission President,
 * Zone Leader, District Leader, etc.) are standard English across all
 * missions regardless of the mission's working language.
 */
function a5a_isLeadershipRow(areaObj) {
  if ((areaObj['Zone'] || '').toUpperCase() === 'ALL') return true;
  var name = String(areaObj['Area_Name'] || '').trim();
  if (/^(Mission President|Assistant to President|Zone Leader|Sister Training Leader -|District Leader -)/i.test(name)) return true;
  return /\bSenior\b/i.test(name);
}
