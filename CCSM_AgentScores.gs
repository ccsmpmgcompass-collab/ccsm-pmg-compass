/**
 * ============================================================
 * CCSM_AgentScores.gs — Scores Engine
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of AgentScores.gs (docs/AgentScores.gs in PMG-Compass), adapted to
 * CCSM's own metric keys and data shape rather than mechanically copied —
 * Provo's version scores against nm_lessons/nm_meaningful/gate/date_metric/
 * etc. (none of which exist in CCSM) and reads its KI values from
 * WEEKLY_BREAKDOWNS (a tab no CCSM agent writes — CCSM's weekly key
 * indicators live in WEEKLY_KI, built by CCSM_Agent5A.gs's a5a_writeWeeklyKI
 * from the Real/Meta columns the missionaries self-report). This mirrors the
 * same "adapt the structure, not the literal metric names" approach already
 * taken by every other forked CCSM agent (e.g. CCSM_Agent5A.gs's WEEKLY_KI
 * rewrite, CCSM_Agent1A.gs's 5-rate-metric REVIEWED DECISION). The Provo
 * file's self-referential baseline/trend scoring system (12-week rolling
 * baseline, ±10 trend nudge) is NOT ported — it is not required by the CCSM
 * design brief, which specifies a single flat SCORE_CONFIG-driven weighted
 * score (see setupCcsmScoreConfig()) — same generic attainment-vs-goal
 * formula (asc_computeScore), simpler goal sourcing.
 *
 * Computes four composite scores per area for the most recently COMPLETED
 * Monday-Sunday week (trigger: Monday 12:05 AM local mission time — see the
 * project plan's trigger table):
 *   Effort Score        (0-100) — weighted nightly activity totals from
 *                                 DAILY_LOG: contacts_attempted, roleplays,
 *                                 member_contacts, effort (Todo/La mayor
 *                                 parte/Algo, converted via ccsmEffortScore())
 *   Skill Score          (0-100) — weighted nightly RATE metrics computed
 *                                 from the week's DAILY_LOG totals: contact_
 *                                 rate, mc_rate, lesson_rate, close_rate
 *                                 (same num/den pairs CCSM_Agent1A.gs uses)
 *   KI Score             (0-100) — weighted average of the 7 ki_*_real
 *                                 values from WEEKLY_KI against that SAME
 *                                 area's own self-reported ki_*_meta goals
 *                                 for the week (no separate goal source needed)
 *   Effectiveness Score  (0-100) — weighted composite of the three above
 *
 * SCORE_CONFIG (two-section layout, mirrors Provo's design):
 *   Section 1 — metric weights:
 *     Area_Code | Metric_Key | Score_Component | Weight | Active
 *   [blank row separator]
 *   Section 2 — per-area effectiveness sub-weights:
 *     Area_Code | Effort_Weight | Skill_Weight | KI_Weight
 *   An Area_Code = 'ALL' row is the mission-wide fallback applied to every
 *   area; any area-specific row (matched by Area_Code) overrides individual
 *   metrics on top of it. setupCcsmScoreConfig() seeds only the 'ALL' rows —
 *   per-area tuning is a manual sheet edit, same as Provo.
 *
 * SCORES tab:
 *   Area_Code | Area_Name | Zone | Missionary_Names | Week_Ending_Date
 *   | Effort_Score | Skill_Score | KI_Score | Effectiveness_Score | Computed_At
 *   Re-running runAgentScores() for the same week REPLACES that week's rows
 *   rather than appending duplicates.
 *
 * Helper prefix: asc_ (all private helpers in this file, matching Provo).
 */


// ── Effort component weights (CCSM design brief defaults) ─────────────────────
var ASC_EFFORT_WEIGHTS = {
  contacts_attempted: 0.30,
  roleplays:          0.20,
  member_contacts:    0.20,
  effort:             0.30
};

// ── Skill component weights — rate metrics (CCSM design brief defaults) ───────
var ASC_SKILL_WEIGHTS = {
  contact_rate: 0.30,
  mc_rate:      0.25,
  lesson_rate:  0.25,
  close_rate:   0.20
};

// ── KI component weights — equal weight over the 7 ki_*_real keys ─────────────
// Built from CCSM_WEEKLY_QUESTIONS (CcsmData.gs) rather than hardcoded, so it
// can never drift from the real WEEKLY_KI columns CCSM_Agent5A.gs writes.
var ASC_KI_WEIGHTS = (function() {
  var w = {};
  CCSM_WEEKLY_QUESTIONS.forEach(function(q) {
    if (q.key.indexOf('ki_') === 0 && q.key.indexOf('_real') === q.key.length - 5) w[q.key] = 1;
  });
  return w;
})();

// ── Default effectiveness sub-weights (CCSM design brief: 0.33/0.33/0.34) ─────
var ASC_DEFAULT_EFFECTIVENESS = { effort: 0.33, skill: 0.33, ki: 0.34 };

// ── Rate metrics — num/den DAILY_LOG keys, mirrors CCSM_Agent1A.gs's
// A1A_RATE_METRICS exactly (same reviewed decision) so Skill Score and the
// Sunday-coaching rate metrics never diverge. defaultTarget/configKey match
// CCSM_AGENT_CONFIG_ROWS' CONTACT_RATE_TARGET/MC_RATE_TARGET/etc.
var ASC_RATE_METRICS = [
  { key: 'contact_rate', num: 'contacts_made',            den: 'contacts_attempted', configKey: 'CONTACT_RATE_TARGET', defaultTarget: 0.50 },
  { key: 'mc_rate',      num: 'meaningful_conversations',  den: 'contacts_made',      configKey: 'MC_RATE_TARGET',      defaultTarget: 0.50 },
  { key: 'lesson_rate',  num: 'friend_lessons',            den: 'contacts_attempted', configKey: 'LESSON_RATE_TARGET',  defaultTarget: 0.20 },
  { key: 'close_rate',   num: 'baptismal_invitations',     den: 'friend_lessons',     configKey: 'CLOSE_RATE_TARGET',   defaultTarget: 0.25 }
];

// ── Default weekly goals for Effort-component raw counts — tunable fallback
// when GOAL_<key> is blank in AGENT_CONFIG (mirrors Provo's ASC_DEFAULT_GOALS
// fallback pattern). 'effort' has no AGENT_CONFIG GOAL_ key (it's a CHOICE
// field, not a count), so it always uses this default unless overridden via
// GOALS_CONFIG.
var ASC_DEFAULT_GOALS = {
  contacts_attempted: 35, // ~5/day
  roleplays:            7, // ~1/day
  member_contacts:     14, // ~2/day
  effort:              14  // ~2 (of 3) average per day x 7
};

// ── SCORE_CONFIG section headers ───────────────────────────────────────────────
var ASC_SECTION1_HEADERS = ['Area_Code', 'Metric_Key', 'Score_Component', 'Weight', 'Active'];
var ASC_SECTION2_HEADERS = ['Area_Code', 'Effort_Weight', 'Skill_Weight', 'KI_Weight', ''];

// ── SCORES tab headers ──────────────────────────────────────────────────────────
var ASC_SCORES_HEADERS = [
  'Area_Code', 'Area_Name', 'Zone', 'Missionary_Names',
  'Week_Ending_Date', 'Effort_Score', 'Skill_Score', 'KI_Score',
  'Effectiveness_Score', 'Computed_At'
];


// ═════════════════════════════════════════════════════════════════════════════
// PUBLIC FUNCTIONS
// ═════════════════════════════════════════════════════════════════════════════

/**
 * setupCcsmScoreConfig()
 * Creates/seeds SCORE_CONFIG with a single mission-wide 'ALL' fallback row
 * set (Section 1 metric weights + Section 2 effectiveness sub-weights),
 * using the CCSM design-brief defaults above. Idempotent — skips the write
 * if the tab already has data rows (same guard as Provo's
 * setupScoreConfigTab()). Users retune weights directly in the sheet
 * afterward; per-area override rows can be added the same way Provo's
 * asc_getAreaConfig() supports (Area_Code matched, 'ALL' applied first).
 */
function setupCcsmScoreConfig() {
  var sheet = getTab('SCORE_CONFIG');

  var existing = sheet.getLastRow() > 0 ? sheet.getDataRange().getValues() : [];
  var dataRowCount = existing.filter(function(r) {
    return r[0] && String(r[0]).trim() !== '' && String(r[0]).trim() !== 'Area_Code';
  }).length;
  if (dataRowCount > 0) {
    Logger.log('AgentScores: SCORE_CONFIG already populated (' + dataRowCount + ' data rows). Skipping.');
    return;
  }

  var rows = [];
  rows.push(ASC_SECTION1_HEADERS);
  Object.keys(ASC_EFFORT_WEIGHTS).forEach(function(k) {
    rows.push(['ALL', k, 'effort', ASC_EFFORT_WEIGHTS[k], 'TRUE']);
  });
  Object.keys(ASC_SKILL_WEIGHTS).forEach(function(k) {
    rows.push(['ALL', k, 'skill', ASC_SKILL_WEIGHTS[k], 'TRUE']);
  });
  Object.keys(ASC_KI_WEIGHTS).forEach(function(k) {
    rows.push(['ALL', k, 'ki', ASC_KI_WEIGHTS[k], 'TRUE']);
  });

  rows.push(['', '', '', '', '']); // section separator

  rows.push(ASC_SECTION2_HEADERS);
  rows.push(['ALL', ASC_DEFAULT_EFFECTIVENESS.effort, ASC_DEFAULT_EFFECTIVENESS.skill, ASC_DEFAULT_EFFECTIVENESS.ki, '']);

  overwriteTab('SCORE_CONFIG', rows);
  Logger.log('AgentScores: SCORE_CONFIG setup complete. ' + rows.length + ' rows written.');
}


/**
 * runAgentScores()
 * Main scoring function — Provo entry-point name kept per the project
 * trigger schedule (Monday 12:05 AM). For each active, non-leadership area:
 *   1. Reads the most recently completed week's DAILY_LOG totals.
 *   2. Reads that same week's WEEKLY_KI row (Real + Meta) for the area.
 *   3. Reads per-area config from SCORE_CONFIG (falls back to the 'ALL' row).
 *   4. Computes Effort, Skill, KI, and Effectiveness scores.
 *   5. Replaces any existing SCORES rows for the week, then writes new ones.
 */
function runAgentScores() {
  var startMs = new Date().getTime();
  var status  = 'SUCCESS';
  var notes   = [];
  var newRows = [];

  try {
    Logger.log('AgentScores: runAgentScores() starting...');

    var tz         = getMissionTimezone();
    var now        = new Date();
    var weekRange  = asc_getCurrentWeekRange(now);
    var computedAt = Utilities.formatDate(now, tz, 'yyyy-MM-dd HH:mm:ss');
    Logger.log('AgentScores: week ' + weekRange.monday + ' to ' + weekRange.sunday);

    var scoresSheet = getTab('SCORES');
    if (scoresSheet.getLastRow() === 0) {
      scoresSheet.getRange(1, 1, 1, ASC_SCORES_HEADERS.length).setValues([ASC_SCORES_HEADERS]);
    } else {
      var firstRow = scoresSheet.getRange(1, 1, 1, ASC_SCORES_HEADERS.length).getValues()[0];
      if (!firstRow[0] || String(firstRow[0]).trim() === '') {
        scoresSheet.getRange(1, 1, 1, ASC_SCORES_HEADERS.length).setValues([ASC_SCORES_HEADERS]);
      }
    }

    var areas       = asc_loadActiveAreas();
    var dailyTotals = asc_loadDailyLogWeek(weekRange.monday, weekRange.sunday);
    var kiByArea    = asc_loadKIForWeek(weekRange.sunday);

    Logger.log('AgentScores: ' + areas.length + ' active area(s), ' +
      Object.keys(dailyTotals).length + ' area(s) with DAILY_LOG activity, ' +
      Object.keys(kiByArea).length + ' area(s) with WEEKLY_KI data.');

    asc_clearScoresForWeek_(scoresSheet, weekRange.sunday);

    areas.forEach(function(area) {
      try {
        var aLower = area.areaName.toLowerCase().trim();
        var config = asc_getAreaConfig(area.areaCode);
        var ew     = config.effectivenessWeights;

        var totals = dailyTotals[aLower] || {};
        var kiRow  = kiByArea[aLower]    || {};

        var effortActuals = {};
        Object.keys(config.fieldWeights.effort).forEach(function(k) { effortActuals[k] = totals[k] || 0; });

        var skillActuals = {};
        ASC_RATE_METRICS.forEach(function(rm) {
          var num = totals[rm.num] || 0;
          var den = totals[rm.den] || 0;
          skillActuals[rm.key] = den > 0 ? (num / den) : 0;
        });

        var kiActuals = {};
        Object.keys(config.fieldWeights.ki).forEach(function(k) { kiActuals[k] = kiRow[k] || 0; });

        var goals = asc_loadAreaGoals(area.areaName, kiRow);

        var effortScore = asc_computeScore(effortActuals, goals, config.fieldWeights.effort);
        var skillScore  = asc_computeScore(skillActuals,  goals, config.fieldWeights.skill);
        var kiScore     = asc_computeScore(kiActuals,     goals, config.fieldWeights.ki);

        var effectivenessScore = asc_round2(
          Math.max(0, Math.min(100, effortScore * ew.effort + skillScore * ew.skill + kiScore * ew.ki))
        );

        newRows.push([
          area.areaCode,
          area.areaName,
          area.zone,
          area.missionaryNames,
          weekRange.sunday,
          asc_round2(effortScore),
          asc_round2(skillScore),
          asc_round2(kiScore),
          effectivenessScore,
          computedAt
        ]);
      } catch (areaErr) {
        Logger.log('AgentScores: ERROR for area ' + area.areaCode + ': ' + areaErr.message);
      }
    });

    if (newRows.length > 0) {
      scoresSheet.getRange(scoresSheet.getLastRow() + 1, 1, newRows.length, newRows[0].length)
                 .setValues(newRows);
      SpreadsheetApp.flush();
    }

    notes.push('SCORES: ' + newRows.length + ' row(s) for week ' + weekRange.sunday);
    Logger.log('AgentScores: runAgentScores() complete — ' + notes.join(' | '));

  } catch (e) {
    status = 'ERROR';
    notes.push('ERROR: ' + e.message);
    Logger.log('AgentScores FATAL: ' + e.message + '\n' + (e.stack || ''));
  }

  logRun('AgentScores', status, newRows.length, 0, new Date().getTime() - startMs, notes.join(' | '));
}


/**
 * setupAgentScoresTrigger()
 * Installs the Monday 12:05 AM local-mission-time trigger for
 * runAgentScores() (see the project trigger schedule). Safe to call multiple
 * times — removes any existing trigger first.
 */
function setupAgentScoresTrigger() {
  deleteTriggerByName('runAgentScores');
  ScriptApp.newTrigger('runAgentScores')
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.MONDAY)
    .atHour(0)
    .nearMinute(5)
    .create();
  Logger.log('AgentScores trigger created: runAgentScores every Monday ~12:05 AM');
}


// ═════════════════════════════════════════════════════════════════════════════
// PRIVATE HELPERS
// ═════════════════════════════════════════════════════════════════════════════

/**
 * asc_getAreaConfig(areaCode)
 * Reads SCORE_CONFIG and returns per-area field weights and effectiveness
 * sub-weights. Falls back to the hardcoded defaults above for any value not
 * present in the sheet. Precedence (low -> high): hardcoded defaults <
 * 'ALL' rows < area-specific rows.
 */
function asc_getAreaConfig(areaCode) {
  var config = {
    fieldWeights: {
      effort: asc_cloneObj(ASC_EFFORT_WEIGHTS),
      skill:  asc_cloneObj(ASC_SKILL_WEIGHTS),
      ki:     asc_cloneObj(ASC_KI_WEIGHTS)
    },
    effectivenessWeights: asc_cloneObj(ASC_DEFAULT_EFFECTIVENESS)
  };

  try {
    var sheet = getTab('SCORE_CONFIG');
    if (sheet.getLastRow() === 0) return config;

    var data = sheet.getDataRange().getValues();
    if (!data || data.length < 2) return config;

    var section1Rows = [];
    var section2Rows = [];
    var pastBlank     = false;
    var inSection2    = false;

    for (var i = 0; i < data.length; i++) {
      var row   = data[i];
      var cell0 = String(row[0] || '').trim();

      if (cell0 === 'Area_Code') continue; // either header row

      if (!cell0 && !pastBlank) {
        pastBlank  = true;
        inSection2 = false;
        continue;
      }
      if (pastBlank && !inSection2 && cell0 === '') continue;
      if (pastBlank && !inSection2 && cell0 !== '') inSection2 = true;

      if (!inSection2) section1Rows.push(row);
      else             section2Rows.push(row);
    }

    var code = String(areaCode).trim().toLowerCase();

    function applySection1(matchCode) {
      section1Rows.forEach(function(r) {
        if (String(r[0] || '').trim().toLowerCase() !== matchCode) return;
        var metricKey = String(r[1] || '').trim();
        var component = String(r[2] || '').trim().toLowerCase();
        var weight    = parseFloat(r[3]) || 0;
        var active    = String(r[4] || '').trim().toUpperCase();
        if (active === 'FALSE') return;
        if (component === 'effort')    config.fieldWeights.effort[metricKey] = weight;
        else if (component === 'skill') config.fieldWeights.skill[metricKey] = weight;
        else if (component === 'ki')    config.fieldWeights.ki[metricKey]    = weight;
      });
    }
    applySection1('all');
    if (code !== 'all') applySection1(code);

    function applySection2(matchCode) {
      section2Rows.forEach(function(r) {
        if (String(r[0] || '').trim().toLowerCase() !== matchCode) return;
        var ew = parseFloat(r[1]);
        var sw = parseFloat(r[2]);
        var kw = parseFloat(r[3]);
        if (!isNaN(ew)) config.effectivenessWeights.effort = ew;
        if (!isNaN(sw)) config.effectivenessWeights.skill  = sw;
        if (!isNaN(kw)) config.effectivenessWeights.ki     = kw;
      });
    }
    applySection2('all');
    if (code !== 'all') applySection2(code);

  } catch (err) {
    Logger.log('AgentScores asc_getAreaConfig ERROR: ' + err.message);
  }

  return config;
}


/**
 * asc_computeScore(actuals, goals, weights)
 * Generic weighted attainment formula, identical to Provo's:
 *   For each weighted metric, min(actual / goal, 1.0) * weight, summed and
 *   normalised so the total weight = 100 (works regardless of whether the
 *   input weights sum to 1.0 or 100 — see the SCORE_CONFIG defaults, which
 *   sum to ~1.0 per the CCSM design brief).
 *
 * @returns {number} Score 0-100
 */
function asc_computeScore(actuals, goals, weights) {
  var totalWeight = 0;
  var earnedScore = 0;

  Object.keys(weights).forEach(function(metric) {
    var w    = weights[metric] || 0;
    var goal = goals[metric];
    if (!goal || goal <= 0) goal = 1;
    var act  = actuals[metric] || 0;

    var attainment = Math.min(act / goal, 1.0);
    earnedScore   += attainment * w;
    totalWeight   += w;
  });

  if (totalWeight <= 0) return 0;

  var score = (earnedScore / totalWeight) * 100;
  return Math.min(score, 100);
}


/**
 * asc_getCurrentWeekRange(refDate)
 * Returns { monday, sunday } ('YYYY-MM-DD') for the most recently completed
 * Monday-Sunday week in mission local time — the week ending on the most
 * recent Sunday (refDate itself when refDate is a Sunday). The Monday
 * 12:05 AM trigger therefore scores the week that ended the previous day.
 */
function asc_getCurrentWeekRange(refDate) {
  var tz      = getMissionTimezone();
  var dateStr = Utilities.formatDate(refDate, tz, 'yyyy-MM-dd');
  var p       = dateStr.split('-');
  var d       = new Date(parseInt(p[0], 10), parseInt(p[1], 10) - 1, parseInt(p[2], 10));
  var dow     = d.getDay(); // 0=Sun..6=Sat

  var sunday = new Date(d.getFullYear(), d.getMonth(), d.getDate() - dow);
  var monday = new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() - 6);

  function fmt(dt) {
    return dt.getFullYear() + '-' + String(dt.getMonth() + 1).padStart(2, '0') + '-' + String(dt.getDate()).padStart(2, '0');
  }
  return { monday: fmt(monday), sunday: fmt(sunday) };
}


/**
 * asc_loadActiveAreas()
 * Reads MISSION_ORG and returns active, non-leadership area objects.
 * Mirrors CCSM_Agent5A.gs's a5a_loadMissionOrg / a5a_isLeadershipRow.
 */
function asc_loadActiveAreas() {
  var sheet = getTab('MISSION_ORG');
  var data  = sheet.getDataRange().getValues();
  if (!data || data.length < 2) return [];

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var areas   = [];

  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    var obj = {};
    headers.forEach(function(h, idx) { obj[h] = (row[idx] != null) ? String(row[idx]).trim() : ''; });

    var isActive = obj['Active'] && obj['Active'].toUpperCase() === 'TRUE';
    if (!isActive || !obj['Area_Name']) continue;
    if (asc_isLeadershipRow(obj)) continue;

    areas.push({
      areaCode:        obj['Area_Code'] || obj['Area_Name'],
      areaName:        obj['Area_Name'],
      zone:            obj['Zone'] || '',
      missionaryNames: [obj['Companion1_Name'], obj['Companion2_Name']].filter(Boolean).join(' & ')
    });
  }

  return areas;
}


/**
 * asc_isLeadershipRow(obj)
 * True for MISSION_ORG leadership tracking rows (never submit, never
 * scored). Mirrors a5a_isLeadershipRow / a3_isLeadershipRow exactly.
 */
function asc_isLeadershipRow(obj) {
  if ((obj['Zone'] || '').toUpperCase() === 'ALL') return true;
  var name = String(obj['Area_Name'] || '').trim();
  if (/^(Mission President|Assistant to President|Zone Leader|Sister Training Leader -|District Leader -)/i.test(name)) return true;
  return /\bSenior\b/i.test(name);
}


/**
 * asc_loadDailyLogWeek(mondayStr, sundayStr)
 * Reads DAILY_LOG and sums, per area, every metric key needed by the Effort
 * and Skill components (ASC_EFFORT_WEIGHTS keys + every ASC_RATE_METRICS
 * num/den key) across [mondayStr, sundayStr]. The 'effort' CHOICE column
 * (Todo/La mayor parte/Algo) is converted to a number via ccsmEffortScore()
 * before summing.
 *
 * @returns {Object} { areaLower: { metricKey: total, ... }, ... }
 */
function asc_loadDailyLogWeek(mondayStr, sundayStr) {
  var totals = {};
  var sheet  = getTab('DAILY_LOG');
  if (!sheet || sheet.getLastRow() === 0) return totals;

  var data = sheet.getDataRange().getValues();
  if (!data || data.length < 2) return totals;

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var dateCol = headers.indexOf('Date');
  var areaCol = headers.indexOf('Area');
  if (dateCol === -1 || areaCol === -1) {
    Logger.log('AgentScores: DAILY_LOG missing Date or Area column.');
    return totals;
  }

  var neededKeys = {};
  Object.keys(ASC_EFFORT_WEIGHTS).forEach(function(k) { neededKeys[k] = true; });
  ASC_RATE_METRICS.forEach(function(rm) { neededKeys[rm.num] = true; neededKeys[rm.den] = true; });

  var colIdx = {};
  Object.keys(neededKeys).forEach(function(k) {
    var ci = headers.indexOf(k);
    if (ci !== -1) colIdx[k] = ci;
  });

  for (var i = 1; i < data.length; i++) {
    var row     = data[i];
    var dateStr = asc_toDateString(row[dateCol]);
    if (!dateStr || dateStr < mondayStr || dateStr > sundayStr) continue;

    var area = String(row[areaCol] || '').trim().toLowerCase();
    if (!area) continue;

    if (!totals[area]) totals[area] = {};
    Object.keys(colIdx).forEach(function(k) {
      var raw = row[colIdx[k]];
      var val = (k === 'effort') ? ccsmEffortScore(String(raw || '').trim()) : (parseFloat(raw) || 0);
      totals[area][k] = (totals[area][k] || 0) + val;
    });
  }

  return totals;
}


/**
 * asc_loadKIForWeek(weekEndStr)
 * Loads the WEEKLY_KI row per area for weekEndStr — falling back to the most
 * recent prior week if that exact week hasn't been written yet (e.g. scores
 * run before CCSM_Agent5A.gs has processed the new week's submissions).
 *
 * @returns {Object} { areaLower: { ki_x_real: v, ki_x_meta: v, ... }, ... }
 */
function asc_loadKIForWeek(weekEndStr) {
  var best  = {};
  var sheet = getTab('WEEKLY_KI');
  if (!sheet || sheet.getLastRow() === 0) return best;

  var data = sheet.getDataRange().getValues();
  if (!data || data.length < 2) return best;

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var weekCol = headers.indexOf('Week_End_Date');
  var areaCol = headers.indexOf('Area');
  if (weekCol === -1 || areaCol === -1) {
    Logger.log('AgentScores: WEEKLY_KI missing Week_End_Date or Area column.');
    return best;
  }

  var kiCols = {};
  headers.forEach(function(h, idx) { if (h.indexOf('ki_') === 0) kiCols[h] = idx; });

  var bestWeek = {}; // areaLower -> week string of the currently-kept row
  for (var i = 1; i < data.length; i++) {
    var row  = data[i];
    var week = asc_toDateString(row[weekCol]);
    var area = String(row[areaCol] || '').trim().toLowerCase();
    if (!week || !area || week > weekEndStr) continue;
    if (bestWeek[area] && bestWeek[area] >= week) continue;

    var vals = {};
    Object.keys(kiCols).forEach(function(k) { vals[k] = parseFloat(row[kiCols[k]]) || 0; });
    best[area]     = vals;
    bestWeek[area] = week;
  }

  return best;
}


/**
 * asc_loadAreaGoals(areaName, kiRow)
 * Builds the full goals object for one area/week, combining:
 *   - Effort-component counts: AGENT_CONFIG GOAL_<key> override, else
 *     ASC_DEFAULT_GOALS, else a per-area GOALS_CONFIG (wide table: Area +
 *     one column per metric key) override if present.
 *   - Skill-component rates: AGENT_CONFIG *_RATE_TARGET (same keys
 *     CCSM_Agent1A.gs reads), else ASC_RATE_METRICS' defaultTarget.
 *   - KI-component: the area's OWN self-reported ki_*_meta value for this
 *     week (from kiRow) — no separate goal source needed. Falls back to 1
 *     (never 0) if missing, matching asc_computeScore's own goal<=0 guard.
 *
 * @param {string} areaName
 * @param {Object} kiRow - this area's WEEKLY_KI row for the scored week
 * @returns {Object} { metricKey: goalValue, ... }
 */
function asc_loadAreaGoals(areaName, kiRow) {
  var goals = asc_cloneObj(ASC_DEFAULT_GOALS);

  // Effort-component AGENT_CONFIG overrides
  Object.keys(ASC_EFFORT_WEIGHTS).forEach(function(metric) {
    try {
      var configVal = getConfig('GOAL_' + metric);
      if (configVal) {
        var num = parseFloat(configVal);
        if (!isNaN(num) && num > 0) goals[metric] = num;
      }
    } catch (e) { /* silent */ }
  });

  // Skill-component rate targets
  ASC_RATE_METRICS.forEach(function(rm) {
    var configVal = getConfig(rm.configKey);
    var num       = configVal ? parseFloat(configVal) : NaN;
    goals[rm.key] = (!isNaN(num) && num > 0) ? num : rm.defaultTarget;
  });

  // Per-area GOALS_CONFIG override (wide table: Area + one column per metric)
  try {
    var sheet = getTab('GOALS_CONFIG');
    if (sheet.getLastRow() > 0) {
      var data = sheet.getDataRange().getValues();
      if (data && data.length > 1) {
        var headers = data[0].map(function(h) { return String(h).trim(); });
        var areaCol = headers.indexOf('Area');
        if (areaCol !== -1) {
          var canon = String(areaName).trim().toLowerCase();
          for (var i = 1; i < data.length; i++) {
            if (String(data[i][areaCol] || '').trim().toLowerCase() !== canon) continue;
            headers.forEach(function(h, idx) {
              if (idx === areaCol || !goals.hasOwnProperty(h)) return;
              var val = parseFloat(data[i][idx]);
              if (!isNaN(val) && val > 0) goals[h] = val;
            });
            break;
          }
        }
      }
    }
  } catch (err) {
    Logger.log('AgentScores asc_loadAreaGoals ERROR: ' + err.message);
  }

  // KI-component: this area's own Meta values for the scored week
  Object.keys(ASC_KI_WEIGHTS).forEach(function(kiKey) {
    var metaKey = kiKey.replace('_real', '_meta');
    var metaVal = kiRow ? parseFloat(kiRow[metaKey]) : NaN;
    goals[kiKey] = (!isNaN(metaVal) && metaVal > 0) ? metaVal : 1;
  });

  return goals;
}


/**
 * asc_clearScoresForWeek_(scoresSheet, weekEndStr)
 * Removes any SCORES rows already written for weekEndStr so re-runs replace
 * the week instead of appending duplicates.
 */
function asc_clearScoresForWeek_(scoresSheet, weekEndStr) {
  var lastRow = scoresSheet.getLastRow();
  if (lastRow < 2) return;

  var data    = scoresSheet.getDataRange().getValues();
  var headers = data[0].map(function(h) { return String(h).trim(); });
  var weekCol = headers.indexOf('Week_Ending_Date');
  if (weekCol === -1) return;

  var keep    = [data[0]];
  var removed = 0;
  for (var i = 1; i < data.length; i++) {
    if (asc_toDateString(data[i][weekCol]) === weekEndStr) { removed++; continue; }
    keep.push(data[i]);
  }
  if (removed === 0) return;

  scoresSheet.clearContents();
  scoresSheet.getRange(1, 1, keep.length, keep[0].length).setValues(keep);
  SpreadsheetApp.flush();
  Logger.log('AgentScores: replaced ' + removed + ' existing SCORES row(s) for week ' + weekEndStr + '.');
}


/**
 * asc_toDateString(val)
 * Converts a Date object, Sheets serial number, or date string to
 * 'YYYY-MM-DD' in mission local time. Returns null if conversion fails.
 * Mirrors a3_toDateString / a5a_toDateString exactly.
 */
function asc_toDateString(val) {
  if (val === null || val === undefined || val === '') return null;

  var d;
  if (val instanceof Date) {
    d = val;
  } else if (typeof val === 'number') {
    d = new Date(Date.UTC(1899, 11, 30) + val * 86400000);
  } else {
    var s = String(val).trim();
    var m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return m[1] + '-' + m[2] + '-' + m[3];
    d = new Date(s);
  }

  if (isNaN(d.getTime())) return null;
  return Utilities.formatDate(d, getMissionTimezone(), 'yyyy-MM-dd');
}


/**
 * asc_round2(num)
 * Rounds a number to 2 decimal places.
 */
function asc_round2(num) {
  return Math.round(num * 100) / 100;
}


/**
 * asc_cloneObj(obj)
 * Shallow-clones a plain object.
 */
function asc_cloneObj(obj) {
  var result = {};
  Object.keys(obj).forEach(function(k) { result[k] = obj[k]; });
  return result;
}
