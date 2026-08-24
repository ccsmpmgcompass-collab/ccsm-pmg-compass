/**
 * ============================================================
 * CCSM_Agent1A.gs — Monday Coaching: Data Collection & Analysis
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
 * SCHEDULE: Every Monday ~9:15-9:30 PM (see CCSM_Setup.gs CCSM_TRIGGER_SCHEDULE)
 *           Run setupAllCcsmTriggers() to install it — setupAgent1ATrigger()
 *           below is a deprecated shim kept only for the editor's dropdown.
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
    Logger.log('Agent1A: Starting Monday coaching analysis -- ' + new Date().toISOString());

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

    // Multi-week data for the trend chart / scoreboard / goal grid /
    // You-vs-You / funnel strip / consistency block (see a1a_buildDerived).
    var derivedWeeks  = a1a_lastNWeekEnds_(weekEnd, 8);
    var history       = a1a_loadMultiWeekHistory(derivedWeeks);
    var transferStart = getConfig('TRANSFER_START_DATE') || '';

    // effort_score has no num/den, so a1a_loadMultiWeekHistory can't derive
    // it from DAILY_LOG sums the way the 4 fraction rates are derived --
    // read it separately from NIGHTLY_FORM_RAW and merge into the same
    // per-area/per-week buckets a1a_buildDerived reads.
    var multiWeekEffort = a1a_loadMultiWeekEffort(derivedWeeks);
    Object.keys(multiWeekEffort).forEach(function(area) {
      if (!history.byArea[area]) return; // no DAILY_LOG activity that area/week; nothing to attach effort_score to
      Object.keys(multiWeekEffort[area]).forEach(function(we) {
        if (history.byArea[area][we]) history.byArea[area][we].effort_score = multiWeekEffort[area][we];
      });
    });

    // Weekly Key Indicators (WEEKLY_KI) -- the 7 real/meta pairs the coaching
    // letter now leads with. Separate from everything above, which is nightly.
    var weeklyKi = a1a_loadWeeklyKi(weekEnd);
    Logger.log('Agent1A: WEEKLY_KI rows for ' + weekEnd + ': ' +
               (weeklyKi === null ? 'TAB UNAVAILABLE' : Object.keys(weeklyKi).length));

    var areaData = {};
    missionOrg.forEach(function(areaObj) {
      var name   = areaObj['Area_Name'];
      var stats  = a1a_buildStats(dailyTotals[name] || {}, effortMap[name] || {});
      var ranked = a1a_rankMetrics(stats, goals[name] || goalDefaults, rateTargets, (feedback[name] || {}).lastGrowthMetric);
      var growth = ranked[ranked.length - 1] || null;

      areaData[name] = {
        code:      areaObj['Area_Code']        || '',
        zone:      areaObj['Zone']             || '',
        district:  areaObj['District']         || '',
        email1:    areaObj['Companion1_Email'] || '',
        email2:    areaObj['Companion2_Email'] || '',
        name1:     areaObj['Companion1_Name']  || '',
        name2:     areaObj['Companion2_Name']  || '',
        stats:     stats,
        // 7 weekly Key Indicators. [] = tab readable but this area filed no
        // weekly form (the letter says so); null = tab unavailable entirely
        // (the letter stays silent rather than blaming the companionship).
        ki:        weeklyKi === null ? null : (weeklyKi[name] || []),
        ranked:    ranked, // full ranked metric list -- the scoreboard needs every goaled metric, not just the 3 picks below
        strength1: ranked[0] || null,
        strength2: ranked[1] || null,
        growth:    growth,
        derived:   a1a_buildDerived(name, stats, growth, history, derivedWeeks, weekEnd, transferStart)
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

/**
 * DEPRECATED — see CCSM_Setup.gs "LEGACY PER-AGENT INSTALLERS". This used to
 * install runAgent1A directly on Monday ~9:15-9:45 PM while
 * CCSM_TRIGGER_SCHEDULE (the canonical table) still said Sunday — running
 * this by mistake would have silently overridden the canonical schedule
 * with a day nobody else's docs agreed with. Now a delegating shim.
 */
function setupAgent1ATrigger() {
  Logger.log('Agent1A: setupAgent1ATrigger() is DEPRECATED — delegating to setupAllCcsmTriggers().');
  setupAllCcsmTriggers();
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

// The 7 weekly Key Indicators, in the order they are reported and taught.
// These come from the WEEKLY form (Agent5A -> WEEKLY_KI), NOT the nightly
// form, so they are the only numbers in the coaching letter that carry the
// companionship's OWN goal ("meta") rather than a mission-configured one.
// Three of them -- sacrament attendance, first-week attendance and RC at
// church -- have no nightly equivalent at all, so without this loader the
// coaching letter can say nothing about them.
var A1A_KI_DEFS = [
  { key: 'ki_new_people',         display: 'Nuevas Personas Encontradas' },
  { key: 'ki_member_lessons',     display: 'Lecciones con Miembros' },
  { key: 'ki_friends_sacrament',  display: 'Amigos en la Reunión Sacramental' },
  { key: 'ki_friends_first_week', display: 'Amigos en la Iglesia (1ra Semana)' },
  { key: 'ki_baptismal_date',     display: 'Amigos con Fecha Bautismal' },
  { key: 'ki_baptized_confirmed', display: 'Bautizados y Confirmados' },
  { key: 'ki_rc_at_church',       display: 'Conversos Recientes en la Iglesia' }
];

/**
 * Per-area weekly Key Indicators for `weekEnd`, as
 *   { areaName: [{ key, display, real, meta }, ...] }
 *
 * Week_End_Date is normalized through a1a_toDateString rather than compared
 * raw: WEEKLY_KI is written by Agent5A as a 'yyyy-MM-dd' string, but a date-
 * formatted column comes back from getValues() as a Date, and comparing those
 * two directly would silently match nothing.
 *
 * Returns NULL (not {}) when the tab is missing or unreadable, so the letter
 * can tell "this companionship didn't submit the weekly form" apart from
 * "the source is unavailable" and word the gap correctly instead of blaming
 * the missionaries for a system problem.
 */
function a1a_loadWeeklyKi(weekEnd) {
  var out  = {};
  var data = a1a_getSheetData('WEEKLY_KI');
  if (!data || data.length < 2) return null;

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var dateIdx = headers.indexOf('Week_End_Date');
  var areaIdx = headers.indexOf('Area');
  if (dateIdx < 0 || areaIdx < 0) return null;

  var cols = {};
  A1A_KI_DEFS.forEach(function(d) {
    cols[d.key] = { real: headers.indexOf(d.key + '_real'), meta: headers.indexOf(d.key + '_meta') };
  });

  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    if (a1a_toDateString(row[dateIdx]) !== weekEnd) continue;
    var area = String(row[areaIdx] || '').trim();
    if (!area) continue;

    out[area] = A1A_KI_DEFS.map(function(d) {
      var c = cols[d.key];
      return {
        key:     d.key,
        display: d.display,
        real:    c.real >= 0 ? (parseFloat(row[c.real]) || 0) : 0,
        meta:    c.meta >= 0 ? (parseFloat(row[c.meta]) || 0) : 0
      };
    });
  }
  return out;
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
 * Maps every date inside any of `weekEnds` (an array of week-ending Sunday
 * date strings) to that week-ending Sunday, so a per-row scan is a single
 * O(1) lookup instead of an N-way range check. Shared by
 * a1a_loadMultiWeekHistory and a1a_loadMultiWeekEffort so both loaders
 * bucket the exact same calendar boundaries -- if they disagreed near a
 * week edge, a nightly report and that same night's effort answer could
 * silently land in different weeks.
 */
function a1a_buildWeekEndForDate_(weekEnds) {
  var map = {};
  weekEnds.forEach(function(we) {
    var start = a1a_getWeekStart(we);
    var startD = a1a_parseLocalDate(start);
    for (var i = 0; i < 7; i++) {
      var d = a1a_toDateString(new Date(startD.getFullYear(), startD.getMonth(), startD.getDate() + i));
      map[d] = we;
    }
  });
  return map;
}

// The 4 rate metrics that are a true 0-1 fraction (num/den). effort_score
// has type:'rate' too but no num/den -- it's a direct 1-3 weighted average,
// not derivable from two DAILY_LOG columns, so it's deliberately excluded
// here and computed instead by a1a_loadMultiWeekEffort from NIGHTLY_FORM_RAW.
var A1A_FRACTION_RATE_KEYS = {};
A1A_RATE_METRICS.forEach(function(m) { if (m.num && m.den) A1A_FRACTION_RATE_KEYS[m.key] = m; });

/**
 * Multi-week analogue of a1a_aggregateDailyLog above, for a1a_buildDerived's
 * trend/scoreboard/goal-grid/You-vs-You/funnel/consistency data. Reads
 * DAILY_LOG ONCE and buckets every row into whichever of `weekEnds` it
 * falls inside, rather than re-scanning the sheet once per week.
 *
 * CRITICAL: after summing the raw per-week columns, this ALSO computes the
 * 4 fraction rate metrics (contact_rate/mc_rate/lesson_rate/close_rate) for
 * every week from those raw sums, via the same num/den formula
 * a1a_buildStats uses for the current week. Skipping this step was a real,
 * shipped bug (found in code review, 2026-08-01): a1a_buildDerived looks up
 * every metric in `stats` -- including these 4 -- as a direct key on each
 * week's bucket. Without this computation, that key never exists for ANY
 * week (current or historical), so a1a_pastWeekValue_ returns undefined
 * for every week, xferVals/allVals only ever contain the CURRENT week's own
 * value, and "Prom. Transfer"/"Tu Mejor" silently render as a copy of THIS
 * WEEK'S number relabeled as historical -- exactly the "silently wrong,
 * presented as normal" failure shape this codebase has been burned by
 * before. tests/test_agent1a_derived.js asserts this explicitly for
 * contact_rate now, not just a count metric.
 *
 * Returns { byArea, datesByArea }:
 *   byArea[area][weekEndStr]      -- raw DAILY_LOG metric sums for that
 *                                     week, PLUS the 4 computed fraction
 *                                     rate keys. effort_score is NOT here --
 *                                     see a1a_loadMultiWeekEffort, merged in
 *                                     by the caller (runAgent1A).
 *   datesByArea[area][dateStr]    -- true for every date the area has a
 *                                     DAILY_LOG row, used by the consistency
 *                                     block's dayFlags/streak.
 */
function a1a_loadMultiWeekHistory(weekEnds) {
  var byArea = {}, datesByArea = {};
  var data = a1a_getSheetData('DAILY_LOG');
  if (!data || data.length < 2) return { byArea: byArea, datesByArea: datesByArea };

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var areaIdx = headers.indexOf('Area');
  var dateIdx = headers.indexOf('Date');
  if (areaIdx < 0 || dateIdx < 0) return { byArea: byArea, datesByArea: datesByArea };

  var weekEndForDate = a1a_buildWeekEndForDate_(weekEnds);

  for (var i = 1; i < data.length; i++) {
    var dateStr = a1a_toDateString(data[i][dateIdx]);
    if (!dateStr) continue;
    var area = String(data[i][areaIdx] || '').trim();
    if (!area) continue;

    if (!datesByArea[area]) datesByArea[area] = {};
    datesByArea[area][dateStr] = true;

    var we = weekEndForDate[dateStr];
    if (!we) continue; // outside the 8-week window this run cares about

    if (!byArea[area]) byArea[area] = {};
    if (!byArea[area][we]) byArea[area][we] = { submissions: 0 };
    byArea[area][we].submissions++;
    headers.forEach(function(h, idx) {
      if (idx < 4) return;
      byArea[area][we][h] = (byArea[area][we][h] || 0) + (parseFloat(data[i][idx]) || 0);
    });
  }

  // Derive the 4 fraction rate metrics per area per week from the raw sums
  // just accumulated, same num/den formula as a1a_buildStats.
  Object.keys(byArea).forEach(function(area) {
    Object.keys(byArea[area]).forEach(function(we) {
      var wk = byArea[area][we];
      Object.keys(A1A_FRACTION_RATE_KEYS).forEach(function(key) {
        var m = A1A_FRACTION_RATE_KEYS[key];
        wk[key] = wk[m.den] > 0 ? (wk[m.num] / wk[m.den]) : 0;
      });
    });
  });

  return { byArea: byArea, datesByArea: datesByArea };
}

/**
 * Multi-week analogue of a1a_readEffortScores above, for the same reason
 * a1a_loadMultiWeekHistory exists: effort_score has no num/den (it's a
 * direct 1-3 weighted average of Todo/La mayor parte/Algo answers), so it
 * cannot be derived from DAILY_LOG sums the way the 4 fraction rates can --
 * it has to be read from NIGHTLY_FORM_RAW per week. Reads the sheet ONCE
 * and buckets by the same weekEndForDate map a1a_loadMultiWeekHistory uses.
 *
 * Returns { area: { weekEndStr: score } }.
 */
function a1a_loadMultiWeekEffort(weekEnds) {
  var byArea = {};
  var data = a1a_getSheetData('NIGHTLY_FORM_RAW');
  if (!data || data.length < 2) return byArea;

  var headers      = data[0].map(function(h) { return String(h).trim(); });
  var areaTarget   = A1A_FORM_AREA_COL.toLowerCase();
  var dateTarget   = A1A_FORM_DATE_COL.toLowerCase();
  var effortTarget = A1A_EFFORT_COL.toLowerCase();

  var areaCols = [];
  headers.forEach(function(h, idx) {
    if (h.toLowerCase() === areaTarget) areaCols.push(idx);
  });
  if (areaCols.length === 0) return byArea;

  var secStart  = areaCols[0];
  var secEnd    = areaCols.length > 1 ? areaCols[1] : headers.length;
  var offsetMap = {};
  for (var j = secStart; j < secEnd; j++) {
    var lh = headers[j].toLowerCase();
    if (!(lh in offsetMap)) offsetMap[lh] = j - secStart;
  }

  var dateOffset   = offsetMap[dateTarget];
  var effortOffset = offsetMap[effortTarget];
  if (dateOffset === undefined || effortOffset === undefined) return byArea;

  var weekEndForDate = a1a_buildWeekEndForDate_(weekEnds);
  var tally = {}; // area -> weekEnd -> {all,most,some,total}

  for (var i = 1; i < data.length; i++) {
    var row  = data[i];
    var sIdx = -1;
    for (var s = 0; s < areaCols.length; s++) {
      if (String(row[areaCols[s]] || '').trim()) { sIdx = areaCols[s]; break; }
    }
    if (sIdx < 0) continue;
    var area    = String(row[sIdx] || '').trim();
    var dateStr = a1a_toDateString(row[sIdx + dateOffset]);
    if (!area || !dateStr) continue;
    var we = weekEndForDate[dateStr];
    if (!we) continue;

    if (!tally[area]) tally[area] = {};
    if (!tally[area][we]) tally[area][we] = { all: 0, most: 0, some: 0, total: 0 };
    var t = tally[area][we];
    t.total++;
    var score = ccsmEffortScore(String(row[sIdx + effortOffset] || '').trim());
    if      (score === 3) t.all++;
    else if (score === 2) t.most++;
    else if (score === 1) t.some++;
  }

  Object.keys(tally).forEach(function(area) {
    byArea[area] = {};
    Object.keys(tally[area]).forEach(function(we) {
      var t = tally[area][we];
      byArea[area][we] = t.total > 0 ? (t.all * 3 + t.most * 2 + t.some * 1) / t.total : 0;
    });
  });
  return byArea;
}

/** N week-ending Sundays, ascending, ending at weekEnd (inclusive). */
function a1a_lastNWeekEnds_(weekEnd, n) {
  var endD = a1a_parseLocalDate(weekEnd);
  var out = [];
  for (var w = n - 1; w >= 0; w--) {
    out.push(a1a_toDateString(new Date(endD.getFullYear(), endD.getMonth(), endD.getDate() - 7 * w)));
  }
  return out;
}

function a1a_pastWeekValue_(metricKey, dailyWeeks, weekEnd) {
  var wk = dailyWeeks[weekEnd];
  return wk ? wk[metricKey] : undefined;
}

// Deliberately returns the UNROUNDED mean -- rounding belongs at the call
// site via a1a_roundForMetric_, which needs to know the metric's key to
// pick the right precision (a 0-1 fraction rate metric needs far finer
// rounding than a plain count/effort_score, see a1a_roundForMetric_'s own
// comment for the bug this fixes).
function a1a_mean_(arr) {
  if (arr.length === 0) return null;
  var s = 0; arr.forEach(function(v) { s += v; });
  return s / arr.length;
}

function a1a_round1(n) {
  return Math.round(n * 10) / 10;
}

/**
 * Rounds a per-metric value to the precision that metric's display format
 * actually needs. CRITICAL: a1a_round1's 0.1 absolute step is correct for
 * count metrics and effort_score (1-3 scale), but applying it to a 0-1
 * fraction rate metric (contact_rate etc.) rounds to the nearest 10
 * PERCENTAGE POINTS -- found in code review, 2026-08-01: a real value of
 * 0.05 (5%) rounded to 0.1 (10%), a 100% relative error, before this fix.
 * Fraction rates instead round to 3 decimals (0.1 percentage-point
 * precision), which a1c_fmtMetricVal_'s own Math.round(val*100) then
 * displays cleanly.
 */
function a1a_roundForMetric_(key, n) {
  if (n === null || n === undefined) return n;
  return A1A_FRACTION_RATE_KEYS[key] ? (Math.round(n * 1000) / 1000) : a1a_round1(n);
}

/**
 * Builds the multi-week comparison data (trend chart / scoreboard / goal
 * grid / You-vs-You / funnel strip / consistency block) for one area's
 * coaching letter. CCSM analogue of Provo's docs/Agent1A.gs
 * a1a_buildDerived, adapted:
 *
 *   - No WEEKLY_BREAKDOWNS input. CCSM's WEEKLY_KI holds only the 7 ki_*
 *     real/meta pairs, not nightly rollups (see this file's own header), so
 *     every multi-week number here comes from DAILY_LOG (via
 *     a1a_loadMultiWeekHistory) alone.
 *   - The funnel is CCSM's real nightly chain — contacts_attempted ->
 *     contacts_made -> meaningful_conversations -> friend_lessons ->
 *     new_people_found — not Provo's doors/LSI shape. CCSM's form has no
 *     LSI metric, so there is no lsiGiven/lsiFollowups field at all (do not
 *     add one — see tests/test_agent1a_derived.js).
 *
 * @param {string}  areaName
 * @param {Object}  stats        this week's a1a_buildStats() output
 * @param {Object}  growth       the ranked growth pick ({key, display, ...})
 *                               or null
 * @param {Object}  history      { byArea, datesByArea } from
 *                               a1a_loadMultiWeekHistory(weeks)
 * @param {Array}   weeks        8 week-ending Sundays, ascending, from
 *                               a1a_lastNWeekEnds_(weekEnd, 8) — MUST be the
 *                               same array passed to a1a_loadMultiWeekHistory
 * @param {string}  weekEnd      this week's ending Sunday (last of `weeks`)
 * @param {string}  transferStart AGENT_CONFIG TRANSFER_START_DATE, or ''
 */
function a1a_buildDerived(areaName, stats, growth, history, weeks, weekEnd, transferStart) {
  var dailyWeeks = history.byArea[areaName] || {};
  var dateSet    = history.datesByArea[areaName] || {};

  // 'effort' is the raw CHOICE-type NIGHTLY_FORM_RAW column ('Todo'/'Algo'/
  // etc) that a1a_buildStats copies through parseFloat()||0 like every
  // other DAILY_LOG column -- it's always 0 and means nothing as a number.
  // effort_score (the real weighted metric) is unaffected; this only skips
  // the raw junk key from ever becoming a tracked "metric."
  var SKIP = { submissions: 1, effort: 1, effort_all: 1, effort_most: 1, effort_some: 1, effort_total: 1 };
  var seen = {};
  var metricKeys = [];
  Object.keys(stats).forEach(function(k) {
    if (SKIP[k] || seen[k]) return;
    if (typeof stats[k] === 'number') { seen[k] = 1; metricKeys.push(k); }
  });

  var lastWk = weeks[weeks.length - 2];
  var histWeekList = Object.keys(dailyWeeks).filter(function(k) { return k !== weekEnd; });

  var prevXferStart = '';
  if (transferStart) {
    var ts = a1a_parseLocalDate(transferStart);
    prevXferStart = a1a_toDateString(new Date(ts.getFullYear(), ts.getMonth(), ts.getDate() - 42));
  }

  var lastWeek = {}, delta = {}, xferAvg = {}, lastXferAvg = {}, best = {}, isBest = {};
  metricKeys.forEach(function(m) {
    var cur = (typeof stats[m] === 'number') ? stats[m] : 0;
    var lv = a1a_pastWeekValue_(m, dailyWeeks, lastWk);
    lastWeek[m] = (lv === undefined) ? null : lv;
    delta[m] = (lv === null || lv === undefined) ? null : a1a_roundForMetric_(m, cur - lv);

    var xferVals = [cur], lastXferVals = [], allVals = [cur];
    histWeekList.forEach(function(wk) {
      var v = a1a_pastWeekValue_(m, dailyWeeks, wk);
      if (v === null || v === undefined) return;
      allVals.push(v);
      if (transferStart && wk >= transferStart) xferVals.push(v);
      else if (prevXferStart && wk >= prevXferStart && wk < transferStart) lastXferVals.push(v);
    });
    xferAvg[m]     = transferStart ? a1a_roundForMetric_(m, a1a_mean_(xferVals)) : null;
    lastXferAvg[m] = a1a_roundForMetric_(m, a1a_mean_(lastXferVals));
    var mx = null;
    allVals.forEach(function(v) { if (mx === null || v > mx) mx = v; });
    best[m] = mx;
    if (allVals.length >= 2 && cur > 0 && cur >= mx) isBest[m] = true;
  });

  var trend = null;
  if (growth) {
    var series = weeks.map(function(wk) {
      var v = (wk === weekEnd) ? ((typeof stats[growth.key] === 'number') ? stats[growth.key] : null)
            : a1a_pastWeekValue_(growth.key, dailyWeeks, wk);
      return { week: wk, value: (v === undefined ? null : v) };
    });
    trend = { key: growth.key, display: growth.display, series: series };
  }

  function pct(num, den) { return den > 0 ? Math.round(num / den * 100) : null; }
  var funnel = {
    attempted:     stats.contacts_attempted || 0,
    contacted:     stats.contacts_made || 0,
    contactedPct:  pct(stats.contacts_made || 0, stats.contacts_attempted || 0),
    meaningful:    stats.meaningful_conversations || 0,
    meaningfulPct: pct(stats.meaningful_conversations || 0, stats.contacts_made || 0),
    lessons:       stats.friend_lessons || 0,
    lessonPct:     pct(stats.friend_lessons || 0, stats.meaningful_conversations || 0),
    newFound:      stats.new_people_found || 0,
    newFoundPct:   pct(stats.new_people_found || 0, stats.friend_lessons || 0),
    lessonsPerNewFriend: (stats.new_people_found || 0) > 0
      ? a1a_round1((stats.friend_lessons || 0) / stats.new_people_found) : null
  };

  // Spanish single-letter weekday initials: Lun Mar Miercoles Jue Vie Sab Dom.
  // 'X' for Miercoles (not 'M') and 'D' for Domingo (not 'S') are the
  // standard Spanish abbreviations that avoid the Mon/Tue and Sat/Sun clash.
  var labels = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];
  var dayFlags = [];
  var startD = a1a_parseLocalDate(weekEnd);
  for (var i = 6; i >= 0; i--) {
    var dayStr = a1a_toDateString(new Date(startD.getFullYear(), startD.getMonth(), startD.getDate() - i));
    dayFlags.push({ label: labels[6 - i], reported: dateSet[dayStr] === true });
  }
  var streak = 0;
  var cursor = a1a_parseLocalDate(weekEnd);
  while (dateSet[a1a_toDateString(cursor)] === true) {
    streak++;
    cursor = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() - 1);
  }
  var consistency = {
    daysReported: stats.submissions || 0,
    dayFlags: dayFlags,
    streak: streak,
    effortAll:  stats.effort_all  || 0,
    effortMost: stats.effort_most || 0,
    effortSome: stats.effort_some || 0
  };

  return { weeks: weeks, lastWeek: lastWeek, delta: delta, xferAvg: xferAvg,
           lastXferAvg: lastXferAvg, best: best, isBest: isBest,
           trend: trend, funnel: funnel, consistency: consistency };
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
