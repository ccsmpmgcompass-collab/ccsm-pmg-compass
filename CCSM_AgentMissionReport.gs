/**
 * ============================================================
 * CCSM_AgentMissionReport.gs — Weekly Mission-Wide Numbers Report
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Phase 6 of the CCSM go-live readiness program. No Provo equivalent —
 * Provo's own nightly report agent was a single-recipient, personal-name-
 * addressed report cut from this fork entirely (a different audience and
 * cadence, and CCSM's own tests/test_no_provo_residue.js forbids naming
 * that cut subsystem in any shipping file). Built fresh, self-contained,
 * following the same one-file-per-agent convention as every other
 * CCSM_Agent*.gs (own date helpers, own DAILY_LOG aggregation — see
 * CCSM_Agent1A.gs's a1a_aggregateDailyLog for the sibling copy this one
 * mirrors; cross-file reuse of another agent's internals is not this
 * codebase's pattern).
 *
 * WHY INDEPENDENT, NOT CHAINED onto Agent1A/1B/1C: that chain's own
 * A1A_DATA/A1B_DATA chain payloads (Drive files, pointed to by a Script
 * Properties key each) are deliberately CLEARED at the end of runAgent1C()
 * (its cleanup step), so a naive scheduleNext() from Agent1C
 * would read empty data. This agent's mission/zone totals are cheap to
 * recompute directly from DAILY_LOG (unlike Agent1A's per-area ranked/
 * derived stats, which are the actual reason 1B/1C stay chained), so
 * independence is both simpler and safer than fighting that cleanup order.
 *
 * SCHEDULE: Monday 10:00 PM mission time (see CCSM_Setup.gs
 *           CCSM_TRIGGER_SCHEDULE) — after AgentScores (Monday 12:05 AM,
 *           same day, so SCORES is fresh) and after the evening coaching
 *           letters (~9:00-9:30 PM), so AP/MP get their personal coaching
 *           email first and this mission-wide view right after.
 *
 * RECIPIENTS: every MISSION_ORG row with Is_AP=TRUE or Is_MP=TRUE, deduped
 * by Companion1_Email/Companion2_Email (same shared-mailbox handling as
 * CCSM_Agent1C.gs's people map — a companionship's area mailbox appears in
 * both slots when there are 2 companions).
 *
 * CONTENT (all Spanish, all CCSM's own metrics):
 *   1. Mission-wide KPI tiles for the week (sums across every active area)
 *   2. Weekly compliance: how many of the mission's areas reported at all
 *   3. Zone-by-zone breakdown table (a mission has ~9 zones vs ~98 areas —
 *      same per-area-tangle lesson as the leader/mission reports on the
 *      Provo side; zone-grouping keeps this readable)
 *   4. Scores summary from the live SCORES tab (AgentScores already ran
 *      that morning): mission averages + the top and bottom 5 areas by
 *      Effectiveness_Score
 *
 * REQUIRED AGENT_CONFIG KEYS: none beyond what every agent already reads
 * (MISSION_TIMEZONE, TEST_MODE / TEST_INBOX_EMAIL via CCSM_AgentTestMode.gs).
 */

// ─── MAIN ENTRY POINT ────────────────────────────────────────────────────────

function runAgentMissionReport() {
  var status = 'SUCCESS';
  var notes  = [];

  try {
    Logger.log('AgentMissionReport: Starting — ' + new Date().toISOString());

    var tz        = getMissionTimezone();
    var now        = new Date();
    var todayStr   = Utilities.formatDate(now, tz, 'yyyy-MM-dd');
    var p          = todayStr.split('-');
    var loc        = new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
    loc.setDate(loc.getDate() - loc.getDay()); // back up to Sunday (getDay: 0=Sun)
    var weekEnd    = amr_toDateString(loc);
    var weekStart  = amr_getWeekStart(weekEnd);

    var missionOrg  = amr_loadMissionOrg();
    if (!missionOrg.length) { Logger.log('AgentMissionReport: MISSION_ORG empty'); return; }

    var dailyTotals = amr_aggregateDailyLog(weekStart, weekEnd);
    var summary      = amr_buildSummary(dailyTotals, missionOrg);
    var scores        = amr_loadScores();

    var recipients = amr_collectApMpRecipients(missionOrg);
    if (recipients.length === 0) {
      notes.push('No AP/MP recipients found (no MISSION_ORG row has Is_AP or Is_MP set)');
      logRun('AgentMissionReport', 'SUCCESS', null, 0, null, notes.join(' | '));
      Logger.log('AgentMissionReport: ' + notes.join(' | '));
      return;
    }

    var subject = amr_buildSubject(weekEnd);
    var body    = amr_buildEmail(weekEnd, summary, scores);

    var emailsSent  = 0;
    var emailErrors = 0;
    var quotaSkipped = 0;

    recipients.forEach(function(email) {
      if (MailApp.getRemainingDailyQuota() < 1) {
        quotaSkipped++;
        return;
      }
      try {
        sendEmail(email, subject, body, 'AgentMissionReport');
        emailsSent++;
      } catch (mailErr) {
        emailErrors++;
        Logger.log('AgentMissionReport: Failed to send to ' + email + ' — ' + mailErr.message);
      }
    });

    notes.push('Week ending ' + weekEnd + ' | Sent: ' + emailsSent + ', errors: ' + emailErrors);

    if (quotaSkipped > 0) {
      status = 'ERROR';
      notes.push('QUOTA EXHAUSTED: ' + quotaSkipped + ' leader(s) received NO mission report.');
    }

    logRun('AgentMissionReport', status, null, emailsSent, null, notes.join(' | '));
    Logger.log('AgentMissionReport: Complete — ' + notes.join(' | '));

  } catch (e) {
    status = 'ERROR';
    notes.push('ERROR: ' + e.message);
    Logger.log('AgentMissionReport FATAL: ' + e.message + '\n' + (e.stack || ''));
    logRun('AgentMissionReport', status, null, null, null, notes.join(' | '));
  }
}

// ─── TRIGGER SETUP ───────────────────────────────────────────────────────────

/**
 * DEPRECATED-ON-ARRIVAL shim, matching every other agent's individual
 * installer (see CCSM_Setup.gs "LEGACY PER-AGENT INSTALLERS") — kept only
 * for the editor's function dropdown, delegates to the canonical installer
 * so it can never drift from CCSM_TRIGGER_SCHEDULE the way three other
 * agents' copies of this exact function already had.
 */
function setupAgentMissionReportTrigger() {
  Logger.log('AgentMissionReport: setupAgentMissionReportTrigger() delegates to setupAllCcsmTriggers().');
  setupAllCcsmTriggers();
}

// ─── DATA LOADERS ────────────────────────────────────────────────────────────

function amr_loadMissionOrg() {
  var data = amr_getSheetData('MISSION_ORG');
  if (!data || data.length < 2) return [];
  var headers = data[0].map(function(h) { return String(h).trim(); });
  var rows = [];
  for (var i = 1; i < data.length; i++) {
    var obj = {};
    headers.forEach(function(h, idx) { obj[h] = data[i][idx]; });
    if (String(obj['Active']).toUpperCase() !== 'TRUE' || !obj['Area_Name']) continue;
    rows.push(obj);
  }
  return rows;
}

/** Same shape/convention as CCSM_Agent1A.gs's a1a_aggregateDailyLog. */
function amr_aggregateDailyLog(weekStart, weekEnd) {
  var data = amr_getSheetData('DAILY_LOG');
  var agg  = {};
  if (!data || data.length < 2) return agg;

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var areaIdx = headers.indexOf('Area');
  var dateIdx = headers.indexOf('Date');
  if (areaIdx < 0 || dateIdx < 0) return agg;

  for (var i = 1; i < data.length; i++) {
    var dateStr = amr_toDateString(data[i][dateIdx]);
    if (!dateStr || dateStr < weekStart || dateStr > weekEnd) continue;
    var area = String(data[i][areaIdx] || '').trim();
    if (!area) continue;
    if (!agg[area]) agg[area] = { submissions: 0 };
    agg[area].submissions++;
    headers.forEach(function(h, idx) {
      if (idx < 4) return; // Date/Area/Zone/District
      agg[area][h] = (agg[area][h] || 0) + (parseFloat(data[i][idx]) || 0);
    });
  }
  return agg;
}

/**
 * Mission-wide + zone-wide totals for the week. Same accumulate-dynamically
 * pattern as CCSM_Agent1A.gs's a1a_buildSummaries (no hardcoded metric
 * list), plus a total_areas/submitted compliance count per scope.
 */
function amr_buildSummary(dailyTotals, missionOrg) {
  var mission = { total_areas: 0, submitted: 0 };
  var zones   = {};

  missionOrg.forEach(function(areaObj) {
    var name = areaObj['Area_Name'];
    var zone = areaObj['Zone'] || '';
    var d    = dailyTotals[name] || {};

    if (!zones[zone]) zones[zone] = { total_areas: 0, submitted: 0 };

    [mission, zones[zone]].forEach(function(s) {
      s.total_areas++;
      if ((d.submissions || 0) > 0) s.submitted++;
      Object.keys(d).forEach(function(k) {
        if (k === 'submissions') return;
        var v = d[k];
        if (typeof v === 'number') s[k] = (s[k] || 0) + v;
      });
    });
  });

  return { mission: mission, zones: zones };
}

/**
 * Reads the SCORES tab and returns { mission: {effort,skill,ki,effectiveness
 * averages}, ranked: [{areaName, zone, effectiveness}, ...] } — one row per
 * area, the LATEST Week_Ending_Date kept when an area appears more than
 * once (SCORES is append-only). Returns null when the tab is empty (no
 * fabricated zeros — see the "Sin datos de puntaje todavia" branch in
 * amr_buildEmail).
 */
function amr_loadScores() {
  var data = amr_getSheetData('SCORES');
  if (!data || data.length < 2) return null;

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var nameIdx = headers.indexOf('Area_Name');
  var zoneIdx = headers.indexOf('Zone');
  var weekIdx = headers.indexOf('Week_Ending_Date');
  var effIdx  = headers.indexOf('Effort_Score');
  var skiIdx  = headers.indexOf('Skill_Score');
  var kiIdx   = headers.indexOf('KI_Score');
  var effcIdx = headers.indexOf('Effectiveness_Score');
  if (nameIdx < 0 || effcIdx < 0) return null;

  var byArea = {};
  for (var i = 1; i < data.length; i++) {
    var row  = data[i];
    var name = String(row[nameIdx] || '').trim();
    if (!name) continue;
    var wk = weekIdx >= 0 ? amr_toDateString(row[weekIdx]) : null;
    if (byArea[name] && byArea[name].week && wk && wk < byArea[name].week) continue;
    byArea[name] = {
      areaName: name,
      zone: zoneIdx >= 0 ? String(row[zoneIdx] || '').trim() : '',
      week: wk,
      effort: effIdx >= 0 ? parseFloat(row[effIdx]) || 0 : 0,
      skill: skiIdx >= 0 ? parseFloat(row[skiIdx]) || 0 : 0,
      ki: kiIdx >= 0 ? parseFloat(row[kiIdx]) || 0 : 0,
      effectiveness: parseFloat(row[effcIdx]) || 0
    };
  }

  var ranked = Object.keys(byArea).map(function(k) { return byArea[k]; });
  if (ranked.length === 0) return null;

  var sums = { effort: 0, skill: 0, ki: 0, effectiveness: 0 };
  ranked.forEach(function(r) {
    sums.effort += r.effort; sums.skill += r.skill; sums.ki += r.ki; sums.effectiveness += r.effectiveness;
  });
  var n = ranked.length;
  var mission = {
    effort: amr_round1(sums.effort / n), skill: amr_round1(sums.skill / n),
    ki: amr_round1(sums.ki / n), effectiveness: amr_round1(sums.effectiveness / n)
  };

  ranked.sort(function(a, b) { return b.effectiveness - a.effectiveness; });

  return { mission: mission, ranked: ranked };
}

function amr_collectApMpRecipients(missionOrg) {
  var emails = {};
  missionOrg.forEach(function(row) {
    var isLeader = String(row['Is_AP']).toUpperCase() === 'TRUE' || String(row['Is_MP']).toUpperCase() === 'TRUE';
    if (!isLeader) return;
    [row['Companion1_Email'], row['Companion2_Email']].forEach(function(email) {
      email = String(email || '').trim().toLowerCase();
      if (!email || email.indexOf('@') < 0) return;
      emails[email] = true;
    });
  });
  return Object.keys(emails);
}

// ─── EMAIL BUILDER ───────────────────────────────────────────────────────────

function amr_buildSubject(weekEnd) {
  return 'PMG Compass — Números de la Misión, semana que termina el ' + amr_formatDate(weekEnd);
}

function amr_buildEmail(weekEnd, summary, scores) {
  var C = { header: '#1e3a5f', green: '#16a34a', blue: '#2563eb', muted: '#6b7280', border: '#e5e7eb', bgLight: '#f9fafb' };
  var m = summary.mission;

  var html = '<div style="font-family:Arial,Helvetica,sans-serif;max-width:680px;margin:0 auto;color:#111;">';
  html += '<div style="background:' + C.header + ';color:white;padding:20px 24px;border-radius:8px 8px 0 0;">' +
          '<div style="font-size:18px;font-weight:700;">PMG Compass — Números de la Misión</div>' +
          '<div style="font-size:12px;opacity:0.75;margin-top:4px;">Semana que termina el ' + amr_esc(amr_formatDate(weekEnd)) + '</div>' +
          '</div>';

  // Compliance
  var pct = m.total_areas > 0 ? Math.round(m.submitted / m.total_areas * 100) : 0;
  html += '<div style="margin:16px 4px;padding:12px 16px;background:' + C.bgLight + ';border-radius:8px;">' +
          '<div style="font-size:20px;font-weight:700;color:' + C.header + ';">' + m.submitted + ' / ' + m.total_areas + ' áreas (' + pct + '%)</div>' +
          '<div style="font-size:11px;color:' + C.muted + ';text-transform:uppercase;letter-spacing:0.05em;">Áreas que reportaron esta semana</div>' +
          '</div>';

  // Mission-wide KPI tiles — every numeric metric the mission collected this week.
  html += '<div style="margin:16px 4px;">';
  html += '<div style="font-size:12px;font-weight:700;color:' + C.header + ';text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">Totales de la Misión</div>';
  html += '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><tr>';
  var tileKeys = Object.keys(m).filter(function(k) { return k !== 'total_areas' && k !== 'submitted' && typeof m[k] === 'number'; }).sort();
  tileKeys.forEach(function(k, i) {
    if (i > 0 && i % 3 === 0) html += '</tr><tr>';
    html += '<td width="33%" style="padding:4px;"><div style="background:' + C.bgLight + ';border-radius:6px;padding:10px 6px;text-align:center;">' +
      '<div style="font-size:18px;font-weight:700;color:' + C.header + ';">' + amr_esc(String(Math.round(m[k]))) + '</div>' +
      '<div style="font-size:9px;color:' + C.muted + ';text-transform:uppercase;">' + amr_esc(amr_metricLabel(k)) + '</div></div></td>';
  });
  html += '</tr></table></div>';

  // Zone-by-zone breakdown
  html += '<div style="margin:16px 4px;">';
  html += '<div style="font-size:12px;font-weight:700;color:' + C.header + ';text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">Por Zona</div>';
  html += '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:11px;">';
  html += '<tr style="background:' + C.header + ';color:#fff;">' +
    '<th style="padding:5px 8px;text-align:left;font-size:10px;">Zona</th>' +
    '<th style="padding:5px 6px;text-align:center;font-size:10px;">Áreas</th>' +
    '<th style="padding:5px 6px;text-align:center;font-size:10px;">Contactos</th>' +
    '<th style="padding:5px 6px;text-align:center;font-size:10px;">Lecciones</th>' +
    '<th style="padding:5px 6px;text-align:center;font-size:10px;">Inv. Baut.</th></tr>';
  Object.keys(summary.zones).sort().forEach(function(zoneName, idx) {
    var z = summary.zones[zoneName];
    var bg = idx % 2 === 0 ? '#ffffff' : C.bgLight;
    html += '<tr style="background:' + bg + ';">' +
      '<td style="padding:4px 8px;border-bottom:1px solid ' + C.border + ';">' + amr_esc(zoneName) + '</td>' +
      '<td style="padding:4px 6px;text-align:center;border-bottom:1px solid ' + C.border + ';">' + z.submitted + '/' + z.total_areas + '</td>' +
      '<td style="padding:4px 6px;text-align:center;border-bottom:1px solid ' + C.border + ';">' + Math.round(z.contacts_made || 0) + '</td>' +
      '<td style="padding:4px 6px;text-align:center;border-bottom:1px solid ' + C.border + ';">' + Math.round(z.friend_lessons || 0) + '</td>' +
      '<td style="padding:4px 6px;text-align:center;border-bottom:1px solid ' + C.border + ';">' + Math.round(z.baptismal_invitations || 0) + '</td>' +
      '</tr>';
  });
  html += '</table></div>';

  // Scores summary
  html += '<div style="margin:16px 4px;">';
  html += '<div style="font-size:12px;font-weight:700;color:' + C.header + ';text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">Resumen de Puntajes</div>';
  if (!scores) {
    html += '<div style="font-size:12px;color:' + C.muted + ';">Sin datos de puntaje todavía.</div>';
  } else {
    html += '<div style="font-size:11px;color:#374151;margin-bottom:10px;">Promedio de la misión — ' +
      'Esfuerzo <strong>' + scores.mission.effort + '</strong> · ' +
      'Habilidad <strong>' + scores.mission.skill + '</strong> · ' +
      'IC <strong>' + scores.mission.ki + '</strong> · ' +
      'Efectividad <strong>' + scores.mission.effectiveness + '</strong></div>';

    function scoreTable(title, rows) {
      var h = '<div style="font-size:10px;font-weight:700;color:' + C.header + ';margin:8px 0 4px;">' + amr_esc(title) + '</div>';
      h += '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:11px;">';
      rows.forEach(function(r) {
        h += '<tr><td style="padding:2px 6px;">' + amr_esc(r.areaName) + ' <span style="color:' + C.muted + ';">(' + amr_esc(r.zone) + ')</span></td>' +
             '<td style="padding:2px 6px;text-align:right;font-weight:700;">' + r.effectiveness + '</td></tr>';
      });
      h += '</table>';
      return h;
    }
    html += scoreTable('Las 5 más altas — Efectividad', scores.ranked.slice(0, 5));
    if (scores.ranked.length > 5) {
      html += scoreTable('Las 5 más bajas — Efectividad', scores.ranked.slice(-5).reverse());
    }
  }
  html += '</div>';

  html += '<div style="margin-top:24px;padding:12px 16px;background:' + C.bgLight + ';border-radius:0 0 8px 8px;font-size:11px;color:' + C.muted + ';text-align:center;">' +
          'PMG Compass — ' + amr_esc(getMissionName()) + '</div>';
  html += '</div>';
  return html;
}

// Metric display labels come from the nightly form itself -- CcsmData.gs's
// CCSM_NIGHTLY_QUESTIONS[].displayEs, the same strings that seed the
// QUESTIONS_CONFIG sheet and that CCSM_Agent1C.gs's a1c_scoreboardLabel_
// resolves.
//
// This used to be a hand-maintained local copy, "matching this codebase's
// per-file self-containment convention". The convention produced silent
// drift: 19 of the 20 labels here disagreed with the form, and two named the
// wrong metric outright -- 'Lecciones CR con Miembro' for the metric that
// counts recent-convert lessons taught with MI SENDA DE LOS CONVENIOS, which
// sat next to 'Lecciones con Miembro' (lessons_member_present) and was
// practically indistinguishable from it.
var _amrNightlyLabels = null;
function amr_nightlyLabels_() {
  if (_amrNightlyLabels) return _amrNightlyLabels;
  var map = {};
  if (typeof CCSM_NIGHTLY_QUESTIONS !== 'undefined') {
    CCSM_NIGHTLY_QUESTIONS.forEach(function(q) {
      if (q.key && q.displayEs) map[q.key] = q.displayEs;
    });
  }
  _amrNightlyLabels = map;
  return map;
}

// Built lazily, never at load time: CcsmData.gs is a separate file and a
// top-level cross-file read is load-order dependent (that pattern already
// caused one production crash here, 2026-08-20).
function amr_metricLabel(key) {
  return amr_nightlyLabels_()[key] || key;
}

// ─── UTILITIES ───────────────────────────────────────────────────────────────

function amr_getSheetData(tabName) {
  var sheet = getTab(tabName);
  if (!sheet || sheet.getLastRow() === 0) return [];
  return sheet.getDataRange().getValues();
}

function amr_toDateString(val) {
  if (val === null || val === undefined || val === '') return null;
  if (typeof val === 'string') {
    var mtch = val.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (mtch) return mtch[1] + '-' + mtch[2] + '-' + mtch[3];
  }
  var d = (val instanceof Date) ? val
    : (typeof val === 'number') ? new Date(Date.UTC(1899, 11, 30) + val * 86400000)
    : new Date(String(val).trim());
  if (isNaN(d.getTime())) return null;
  return Utilities.formatDate(d, getMissionTimezone(), 'yyyy-MM-dd');
}

function amr_parseLocalDate(str) {
  var parts = str.split('-');
  return new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
}

function amr_getWeekStart(sundayStr) {
  var d = amr_parseLocalDate(sundayStr);
  return amr_toDateString(new Date(d.getFullYear(), d.getMonth(), d.getDate() - 6));
}

function amr_round1(n) {
  return Math.round(n * 10) / 10;
}

function amr_formatDate(dateStr) {
  var months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  var m = String(dateStr || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return dateStr;
  return parseInt(m[3], 10) + ' de ' + months[parseInt(m[2], 10) - 1] + ' de ' + m[1];
}

function amr_esc(str) {
  return String(str || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
