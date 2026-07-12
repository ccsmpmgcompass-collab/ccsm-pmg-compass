/**
 * ============================================================
 * CCSM_Agent1A.gs — Sunday Coaching: Data Collection & Analysis
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of Agent1A.gs (docs/Agent1A.gs in PMG-Compass) for the CCSM Spanish
 * form set. Internal a1a_* function names are kept identical to the Provo
 * original so future diffs stay readable; the form column constants, the
 * timezone source, and the coaching-metric definitions are changed to
 * Spanish/CCSM equivalents.
 *
 * REVIEWED DECISION — RATE METRICS: CCSM has no doors/knock metric, so
 * Provo's 6 rate metrics (one of which is a doors-based knock ratio) become
 * CCSM's 5: contact_rate, mc_rate, lesson_rate, close_rate,
 * effort_score. All four ratio metrics are computed entirely from DAILY_LOG
 * aggregates (contacts_attempted/contacts_made/meaningful_conversations/
 * friend_lessons/baptismal_invitations — see A1A_RATE_METRICS num/den keys
 * below) — unlike Provo's close_rate, none depend on WEEKLY_FORM_RAW, so
 * a1a_readWeeklyForm (Provo's English weekly-KI parser: pew/date_metric/
 * gate/renew) has no CCSM equivalent metric key and is dropped entirely
 * (see a1a_buildStats).
 *
 * SCHEDULE: Every Sunday at 9:00 PM
 *           Run setupAgent1ATrigger() ONCE to create the trigger.
 *
 * WHAT IT DOES:
 *   1. Reads current week (Mon-Sun) from DAILY_LOG
 *   2. For each active MISSION_ORG area computes the 5 rate metrics above
 *      plus dynamic count metrics loaded from QUESTIONS_CONFIG (NIGHTLY
 *      NUMBER metrics only — see a1a_loadCountMetrics) and their % of goal
 *   3. Selects 2 strength metrics and 1 growth metric per area
 *      (avoids repeating last week's growth metric per FEEDBACK_HISTORY)
 *   4. Builds mission-wide, zone, and district weekly summaries
 *   5. Saves all data to Script Properties via saveTempData()
 *   6. Schedules Agent1B in 60 seconds
 *
 * CHAINS TO: Agent1B (60 seconds)
 * NO GEMINI, NO EMAIL.
 */

// --- COACHING METRIC DEFINITIONS -------------------------------------------

// Rate metrics — always computed regardless of flavor. This exact array
// (display text, configKey, defaultTarget, pmg, scripture, num/den keys) is
// a reviewed decision — see file header note above. num/den are DAILY_LOG
// metric keys (CCSM_NIGHTLY_QUESTIONS in CcsmData.gs); effort_score has no
// num/den — it is set directly from the weighted Todo/La mayor parte/Algo
// average in a1a_readEffortScores().
var A1A_RATE_METRICS = [
  { key: 'contact_rate', display: 'Tasa de Contacto', type: 'rate',
    configKey: 'CONTACT_RATE_TARGET', defaultTarget: 0.50, pmg: '157', scripture: 'D. y C. 4:4-5',
    num: 'contacts_made', den: 'contacts_attempted' },
  { key: 'mc_rate', display: 'Tasa de Conversaciones Significativas', type: 'rate',
    configKey: 'MC_RATE_TARGET', defaultTarget: 0.50, pmg: '85', scripture: 'D. y C. 11:21',
    num: 'meaningful_conversations', den: 'contacts_made' },
  { key: 'lesson_rate', display: 'Tasa de Lecciones', type: 'rate',
    configKey: 'LESSON_RATE_TARGET', defaultTarget: 0.20, pmg: '174', scripture: 'Alma 26:22',
    num: 'friend_lessons', den: 'contacts_attempted' },
  { key: 'close_rate', display: 'Tasa de Invitación Bautismal', type: 'rate',
    configKey: 'CLOSE_RATE_TARGET', defaultTarget: 0.25, pmg: '205', scripture: 'Moroni 10:4',
    num: 'baptismal_invitations', den: 'friend_lessons' },
  { key: 'effort_score', display: 'Nivel de Esfuerzo', type: 'rate',
    configKey: 'EFFORT_SCORE_TARGET', defaultTarget: 2.75, pmg: null, scripture: null }
];

// Count metrics are built dynamically from QUESTIONS_CONFIG at runtime.
// Initialized in runAgent1A() via a1a_loadCountMetrics().
var A1A_METRICS = null;

// Header constants — must match the exact question text in the CCSM Spanish
// Google Forms (DailyReportForm_ES.gs / WeeklyReportForm_ES.gs /
// CcsmData.gs CCSM_FORM_STRUCTURAL / CCSM_NIGHTLY_QUESTIONS).
var A1A_FORM_AREA_COL   = '¿En qué área sirve?';
var A1A_FORM_DATE_COL   = '¿Qué fecha está ingresando?';
var A1A_EFFORT_COL      = '¿Dio todo, la mayor parte o algo de esfuerzo en el altar del sacrificio hoy?';
var A1A_WEEKLY_AREA_COL = '¿En qué área sirve?';
var A1A_WEEKLY_DATE_COL = '¿Qué fecha está ingresando?';

// --- MAIN ENTRY POINT -------------------------------------------------------

function runAgent1A() {
  // Wait until 9:15 PM before processing -- gives missionaries until 9:15 to submit.
  // Utilities.sleep is capped at 5 min and this account's execution limit is
  // 6 min, so cap the wait at 4 min. The trigger aims for ~9:30 (see
  // setupAgent1ATrigger), so this path is only a fallback for early firings.
  var _tz = getMissionTimezone();
  var _h = Number(Utilities.formatDate(new Date(), _tz, 'H'));
  var _m = Number(Utilities.formatDate(new Date(), _tz, 'm'));
  if (_h === 21 && _m < 15) Utilities.sleep(Math.min(15 - _m, 4) * 60 * 1000);

  var status = 'SUCCESS';
  var notes  = [];

  try {
    Logger.log('Agent1A: Starting Sunday coaching analysis -- ' + new Date().toISOString());

    A1A_METRICS = A1A_RATE_METRICS.concat(a1a_loadCountMetrics());
    Logger.log('Agent1A: Loaded ' + A1A_METRICS.length + ' coaching metrics (' +
               A1A_RATE_METRICS.length + ' rate, ' + (A1A_METRICS.length - A1A_RATE_METRICS.length) + ' count)');

    var missionOrg   = a1a_loadMissionOrg();
    var goals        = a1a_loadGoals();
    var goalDefaults = a1a_loadGoalDefaults();
    var feedback     = a1a_loadFeedbackHistory();
    var rateTargets  = a1a_loadRateTargets();

    // Most recent Sunday in the mission's timezone (works when run Monday)
    var _now      = new Date();
    var _todayStr = Utilities.formatDate(_now, _tz, 'yyyy-MM-dd');
    var _p        = _todayStr.split('-');
    var _loc      = new Date(parseInt(_p[0]), parseInt(_p[1]) - 1, parseInt(_p[2]));
    _loc.setDate(_loc.getDate() - _loc.getDay()); // back up to Sunday (getDay: 0=Sun, 1=Mon, ...)
    var weekEnd   = a1a_toDateString(_loc);
    var weekStart = a1a_getWeekStart(weekEnd);
    Logger.log('Agent1A: Week ' + weekStart + ' to ' + weekEnd);

    var dailyTotals = a1a_aggregateDailyLog(weekStart, weekEnd);
    var effortMap   = a1a_readEffortScores(weekStart, weekEnd);

    var areaData = {};
    missionOrg.forEach(function(areaObj) {
      var name   = areaObj['Area_Name'];
      var stats  = a1a_buildStats(dailyTotals[name] || {}, effortMap[name] || {});
      var ranked = a1a_rankMetrics(stats, goals[name] || goalDefaults, rateTargets, (feedback[name] || {}).lastGrowthMetric);

      areaData[name] = {
        code:      areaObj['Area_Code']        || '',
        zone:      areaObj['Zone']             || '',
        district:  areaObj['District']         || '',
        email1:    areaObj['Companion1_Email'] || '',
        email2:    areaObj['Companion2_Email'] || '',
        name1:     areaObj['Companion1_Name']  || '',
        name2:     areaObj['Companion2_Name']  || '',
        stats:     stats,
        strength1: ranked[0]                 || null,
        strength2: ranked[1]                 || null,
        growth:    ranked[ranked.length - 1] || null
      };
    });

    var summaries = a1a_buildSummaries(areaData, missionOrg);

    saveTempData('A1A_DATA', {
      weekStart: weekStart,
      weekEnd:   weekEnd,
      areas:     areaData,
      summaries: summaries
    });

    notes.push('Analyzed ' + missionOrg.length + ' areas for week ending ' + weekEnd);
    scheduleNext('runAgent1B', 1);
    notes.push('Agent1B scheduled in ~1 min');
    Logger.log('Agent1A: Complete -- ' + notes.join(' | '));

  } catch (e) {
    status = 'ERROR';
    notes.push('ERROR: ' + e.message);
    Logger.log('Agent1A FATAL: ' + e.message + '\n' + (e.stack || ''));
  }

  // logRun(agent, status, recordsProcessed, emailsSent, durationMs, notes, error)
  logRun('Agent1A', status, null, null, null, notes.join(' | '));
}

// --- TRIGGER SETUP ----------------------------------------------------------

function setupAgent1ATrigger() {
  deleteTriggerByName('runAgent1A');
  ScriptApp.newTrigger('runAgent1A')
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.MONDAY)
    .atHour(21)
    .nearMinute(30)  // aim past 9:15 so the wait-until-9:15 sleep (capped at
                     // 4 min; execution limit is 6 min) rarely engages
    .create();
  Logger.log('Agent1A trigger created: runAgent1A every Monday ~9:15-9:45 PM');
}

// --- DATA LOADERS -----------------------------------------------------------

function a1a_loadMissionOrg() {
  var data = a1a_getSheetData('MISSION_ORG');
  if (!data || data.length < 2) throw new Error('MISSION_ORG empty');
  var headers = data[0].map(function(h) { return String(h).trim(); });
  var rows = [];
  for (var i = 1; i < data.length; i++) {
    var obj = {};
    headers.forEach(function(h, idx) { obj[h] = String(data[i][idx] || '').trim(); });
    if (obj['Active'].toUpperCase() !== 'TRUE' || !obj['Area_Name']) continue;
    if (a1a_isLeadershipRow(obj)) continue;
    rows.push(obj);
  }
  return rows;
}

/**
 * Mission-wide default weekly goals for count metrics, read from
 * AGENT_CONFIG's GOAL_<Metric_Key> rows (CcsmData.gs CCSM_AGENT_CONFIG_ROWS
 * has one such row per NIGHTLY NUMBER metric). Used when GOALS_CONFIG has no
 * row for an area — without this fallback an empty GOALS_CONFIG zeroes every
 * count-metric goal, so Sunday coaching can only ever rank the rate metrics.
 */
function a1a_loadGoalDefaults() {
  var defaults = {};
  A1A_METRICS.filter(function(m) { return m.type === 'count'; }).forEach(function(m) {
    defaults[m.goalsKey] = parseFloat(getConfig('GOAL_' + m.goalsKey)) || 0;
  });
  return defaults;
}

/**
 * Count metrics are the NIGHTLY, numeric (Data_Type='NUMBER') rows of
 * QUESTIONS_CONFIG — this excludes report_date (DATE), exchanges (YESNO),
 * and effort (CHOICE), none of which have a meaningful weekly sum, and
 * excludes WEEKLY rows (the self-reported ki_* Real/Meta key indicators,
 * which are absolute values, not daily counts to sum).
 */
function a1a_loadCountMetrics() {
  var data = a1a_getSheetData('QUESTIONS_CONFIG');
  if (!data || data.length < 2) return [];
  var h       = data[0].map(function(c) { return String(c).trim(); });
  var keyIdx  = h.indexOf('Metric_Key');
  var nameIdx = h.indexOf('Metric_Display_Name');
  var actIdx  = h.indexOf('Active');
  var typeIdx = h.indexOf('Data_Type');
  var formIdx = h.indexOf('Form_Type');
  if (keyIdx < 0) return [];
  var metrics = [];
  for (var i = 1; i < data.length; i++) {
    if (actIdx  >= 0 && String(data[i][actIdx]  || '').trim().toUpperCase() !== 'TRUE') continue;
    if (typeIdx >= 0 && String(data[i][typeIdx] || '').trim().toUpperCase() !== 'NUMBER') continue;
    if (formIdx >= 0) {
      var formType = String(data[i][formIdx] || '').trim().toUpperCase();
      if (formType !== 'NIGHTLY' && formType !== '') continue;
    }
    var key  = String(data[i][keyIdx]  || '').trim();
    var name = nameIdx >= 0 ? String(data[i][nameIdx] || '').trim() : key;
    if (!key) continue;
    metrics.push({ key: key, display: name, type: 'count', goalsKey: key, pmg: null, scripture: null });
  }
  return metrics;
}

function a1a_loadGoals() {
  var data = a1a_getSheetData('GOALS_CONFIG');
  var goals = {};
  if (!data || data.length < 2) return goals;
  var headers = data[0].map(function(h) { return String(h).trim(); });
  var areaIdx = headers.indexOf('Area');
  if (areaIdx < 0) return goals;
  var countKeys = A1A_METRICS.filter(function(m) { return m.type === 'count'; }).map(function(m) { return m.goalsKey; });
  var colIdxs = {};
  countKeys.forEach(function(k) { colIdxs[k] = headers.indexOf(k); });
  for (var i = 1; i < data.length; i++) {
    var area = String(data[i][areaIdx] || '').trim();
    if (!area) continue;
    goals[area] = {};
    countKeys.forEach(function(k) {
      var idx = colIdxs[k];
      goals[area][k] = idx >= 0 ? (parseFloat(data[i][idx]) || 0) : 0;
    });
  }
  return goals;
}

function a1a_loadFeedbackHistory() {
  var data = a1a_getSheetData('FEEDBACK_HISTORY');
  var hist = {};
  if (!data || data.length < 2) return hist;
  var headers   = data[0].map(function(h) { return String(h).trim(); });
  var areaIdx   = headers.indexOf('Area_Name');
  if (areaIdx < 0) areaIdx = headers.indexOf('Area');
  var catIdx    = headers.indexOf('Category');
  var growthIdx = headers.indexOf('Last_Growth_Metric');
  if (areaIdx < 0) return hist;

  for (var i = 1; i < data.length; i++) {
    var area     = String(data[i][areaIdx] || '').trim();
    var category = catIdx >= 0 ? String(data[i][catIdx] || '').trim().toUpperCase() : '';
    if (!area) continue;
    if (!hist[area]) hist[area] = { lastGrowthMetric: '' };
    if (category === 'SUNDAY_COACHING_GROWTH' && growthIdx >= 0) {
      hist[area].lastGrowthMetric = String(data[i][growthIdx] || '').trim();
    }
  }
  return hist;
}

function a1a_loadRateTargets() {
  var targets = {};
  A1A_METRICS.filter(function(m) { return m.type === 'rate'; }).forEach(function(m) {
    var raw = getConfig(m.configKey);
    targets[m.key] = raw ? (parseFloat(raw) || m.defaultTarget) : m.defaultTarget;
  });
  return targets;
}

// --- DATA AGGREGATION -------------------------------------------------------

function a1a_aggregateDailyLog(weekStart, weekEnd) {
  var data = a1a_getSheetData('DAILY_LOG');
  var agg  = {};
  if (!data || data.length < 2) return agg;

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var areaIdx = headers.indexOf('Area');
  var dateIdx = headers.indexOf('Date');
  if (areaIdx < 0 || dateIdx < 0) return agg;

  for (var i = 1; i < data.length; i++) {
    var dateStr = a1a_toDateString(data[i][dateIdx]);
    if (!dateStr || dateStr < weekStart || dateStr > weekEnd) continue;
    var area = String(data[i][areaIdx] || '').trim();
    if (!area) continue;
    if (!agg[area]) agg[area] = { submissions: 0 };
    agg[area].submissions++;
    // Copy every DAILY_LOG metric column dynamically (Date/Area/Zone/District
    // are the first 4 columns — see CCSM_Agent3.gs a3_updateDailyLog). Any
    // metric added to QUESTIONS_CONFIG (and therefore DAILY_LOG) is picked up
    // automatically without code changes. Non-numeric columns (exchanges:
    // 'TRUE'/''; effort: 'Todo'/'La mayor parte'/'Algo') parse to 0 here and
    // are simply unused — they never appear as a count-metric key (see
    // a1a_loadCountMetrics' Data_Type==='NUMBER' filter).
    headers.forEach(function(h, idx) {
      if (idx < 4) return;
      agg[area][h] = (agg[area][h] || 0) + (parseFloat(data[i][idx]) || 0);
    });
  }
  return agg;
}

/**
 * Scans NIGHTLY_FORM_RAW for the given week and returns, per area, the
 * Todo/La mayor parte/Algo breakdown and weighted effort_score average.
 * Handles the multi-section form structure (one section per zone) the same
 * way as CCSM_Agent3.gs's a3_parseSectionStructure.
 *
 * Classification uses ccsmEffortScore() (CCSM_Helpers.gs) rather than
 * hardcoded string comparison, so the all/most/some buckets and the
 * weighted average below share one source of truth for what each raw
 * Spanish answer is worth.
 */
function a1a_readEffortScores(weekStart, weekEnd) {
  var data   = a1a_getSheetData('NIGHTLY_FORM_RAW');
  var result = {};
  if (!data || data.length < 2) return result;

  var headers      = data[0].map(function(h) { return String(h).trim(); });
  var areaTarget   = A1A_FORM_AREA_COL.toLowerCase();
  var dateTarget   = A1A_FORM_DATE_COL.toLowerCase();
  var effortTarget = A1A_EFFORT_COL.toLowerCase();

  var areaCols = [];
  headers.forEach(function(h, idx) {
    if (h.toLowerCase() === areaTarget) areaCols.push(idx);
  });
  if (areaCols.length === 0) return result;

  var secStart  = areaCols[0];
  var secEnd    = areaCols.length > 1 ? areaCols[1] : headers.length;
  var offsetMap = {};
  for (var j = secStart; j < secEnd; j++) {
    var lh = headers[j].toLowerCase();
    if (!(lh in offsetMap)) offsetMap[lh] = j - secStart;
  }

  var dateOffset   = offsetMap[dateTarget];
  var effortOffset = offsetMap[effortTarget];
  if (dateOffset === undefined || effortOffset === undefined) return result;

  for (var i = 1; i < data.length; i++) {
    var row  = data[i];
    var sIdx = -1;
    for (var s = 0; s < areaCols.length; s++) {
      if (String(row[areaCols[s]] || '').trim()) { sIdx = areaCols[s]; break; }
    }
    if (sIdx < 0) continue;
    var area    = String(row[sIdx] || '').trim();
    var dateStr = a1a_toDateString(row[sIdx + dateOffset]);
    if (!area || !dateStr || dateStr < weekStart || dateStr > weekEnd) continue;
    if (!result[area]) result[area] = { all: 0, most: 0, some: 0, total: 0, score: 0 };
    result[area].total++;
    var score = ccsmEffortScore(String(row[sIdx + effortOffset] || '').trim());
    if      (score === 3) result[area].all++;   // Todo
    else if (score === 2) result[area].most++;  // La mayor parte
    else if (score === 1) result[area].some++;  // Algo
  }
  Object.keys(result).forEach(function(area) {
    var e = result[area];
    e.score = e.total > 0 ? (e.all * 3 + e.most * 2 + e.some * 1) / e.total : 0;
  });
  return result;
}

// --- STATS & RANKING --------------------------------------------------------

function a1a_buildStats(daily, effort) {
  // Seed with non-metric tracking fields first so they're not double-added below
  var s = {
    submissions: daily.submissions || 0
  };
  // Copy all daily metric totals dynamically — any metric in QUESTIONS_CONFIG
  // (and therefore DAILY_LOG) is automatically included without code changes.
  Object.keys(daily).forEach(function(k) {
    if (k === 'submissions') return;
    if (s[k] === undefined) s[k] = daily[k] || 0;
  });
  // Effort breakdown
  s.effort_all   = effort.all   || 0;
  s.effort_most  = effort.most  || 0;
  s.effort_some  = effort.some  || 0;
  s.effort_total = effort.total || 0;
  s.effort_score = effort.score || 0;
  // Derived rates — computed generically off A1A_RATE_METRICS' num/den keys
  // (the reviewed decision: contact_rate/mc_rate/lesson_rate/close_rate, all
  // sourced from DAILY_LOG aggregates above). effort_score has no num/den —
  // it was already set directly from the weighted average above.
  A1A_RATE_METRICS.forEach(function(m) {
    if (!m.num || !m.den) return;
    s[m.key] = s[m.den] > 0 ? (s[m.num] / s[m.den]) : 0;
  });
  return s;
}

function a1a_rankMetrics(stats, areaGoals, rateTargets, lastGrowthMetric) {
  var ranked = [];
  A1A_METRICS.forEach(function(m) {
    var actual = stats[m.key] || 0;
    var goal   = m.type === 'rate'
      ? (rateTargets[m.key] || m.defaultTarget)
      : ((areaGoals && areaGoals[m.goalsKey]) || 0);

    if (goal <= 0) return;
    ranked.push({ key: m.key, display: m.display, actual: actual, goal: goal,
                  pct: actual / goal, pmg: m.pmg, scripture: m.scripture });
  });

  ranked.sort(function(a, b) { return b.pct - a.pct; });

  if (lastGrowthMetric && ranked.length >= 2) {
    var last = ranked.length - 1;
    if (ranked[last].key === lastGrowthMetric) {
      var tmp = ranked[last]; ranked[last] = ranked[last - 1]; ranked[last - 1] = tmp;
    }
  }
  return ranked;
}

// --- SUMMARIES --------------------------------------------------------------

function a1a_buildSummaries(areaData, missionOrg) {
  var mission   = a1a_emptySummary();
  var zones     = {};
  var districts = {};

  missionOrg.forEach(function(areaObj) {
    var name     = areaObj['Area_Name'];
    var zone     = areaObj['Zone']     || '';
    var district = areaObj['District'] || '';
    var d        = (areaData[name] && areaData[name].stats) || {};

    if (!zones[zone])         zones[zone]         = a1a_emptySummary();
    if (!districts[district]) districts[district] = a1a_emptySummary();

    [mission, zones[zone], districts[district]].forEach(function(s) {
      s.total_areas++;
      if ((d.submissions || 0) > 0) s.submitted++;
      // Accumulate all numeric stats dynamically — no hardcoded metric list
      Object.keys(d).forEach(function(k) {
        if (k === 'submissions') return;
        var v = d[k];
        if (typeof v === 'number') s[k] = (s[k] || 0) + v;
      });
    });
  });

  return { mission: mission, zones: zones, districts: districts };
}

function a1a_emptySummary() {
  return { total_areas: 0, submitted: 0 };
}

// --- UTILITIES --------------------------------------------------------------

function a1a_getSheetData(tabName) {
  var sheet = getTab(tabName);
  if (!sheet || sheet.getLastRow() === 0) return [];
  return sheet.getDataRange().getValues();
}

function a1a_toDateString(val) {
  if (val === null || val === undefined || val === '') return null;
  // yyyy-MM-dd strings must be taken literally — new Date('yyyy-MM-dd') parses
  // as UTC midnight, which is the PREVIOUS day in the mission's timezone.
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

function a1a_parseLocalDate(str) {
  var p = str.split('-');
  return new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
}

function a1a_getWeekStart(sundayStr) {
  var d = a1a_parseLocalDate(sundayStr);
  return a1a_toDateString(new Date(d.getFullYear(), d.getMonth(), d.getDate() - 6));
}

function a1a_isLeadershipRow(obj) {
  // Keyed off Area_Name — NOT the Is_ZL/Is_STL/Is_DL/Is_AP/Is_MP flags, which
  // are legitimately TRUE on real teaching areas whose companionship holds the
  // calling. Mirrors a3_isLeadershipRow (CCSM_Agent3.gs) and a5a_isLeadershipRow
  // (CCSM_Agent5A.gs). IMOS role titles (Mission President, Zone Leader,
  // District Leader, etc.) are standard English across all missions
  // regardless of the mission's working language.
  if ((obj['Zone'] || '').toUpperCase() === 'ALL') return true;
  var name = String(obj['Area_Name'] || '').trim();
  if (/^(Mission President|Assistant to President|Zone Leader|Sister Training Leader -|District Leader -)/i.test(name)) return true;
  return /\bSenior\b/i.test(name);
}
