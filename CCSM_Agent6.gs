/**
 * ============================================================
 * CCSM_Agent6.gs — Friday Encouragement Email Sender (Spanish)
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of Agent6.gs (docs/Agent6.gs in PMG-Compass) for the CCSM Spanish
 * form set. Internal a6_* function names are kept identical to the Provo
 * original so future diffs stay readable; the email templates are Spanish
 * (never AI-generated — see below), and routing/timezone/mission-name
 * literals are read from CCSM_Helpers.gs instead of being hardcoded.
 *
 * CHAINED FROM: Agent5B (~1 minute after Agent5B)
 *
 * WHAT IT DOES:
 *   1. Loads qualifying area data saved by Agent5B from Script Properties
 *   2. Sends one Spanish encouragement email per qualifying area (to both
 *      companions) via sendEmail(..., 'Agent6') — routes through Relay 2
 *      when RELAY_2_URL is configured, else falls back to the main account
 *   3. Email body = pre-written MESSAGE_BANK text only — no AI-generated text
 *   4. Writes to ENCOURAGEMENT_HISTORY (one row per area per week)
 *   5. Sends a summary email to SEND_FROM_EMAIL (AGENT_CONFIG) showing how
 *      many areas qualified and which metrics triggered them
 *   6. Cleans up Script Properties (A5B_DATA)
 *   7. Logs to AGENT_RUN_LOG
 */

// ─── MAIN ENTRY POINT ────────────────────────────────────────────────────────

function runAgent6() {
  var status = 'SUCCESS';
  var notes  = [];

  try {
    Logger.log('Agent6: Starting encouragement send — ' + new Date().toISOString());

    // loadTempData() already parses the JSON it stored, so payload is the
    // object saveTempData('A5B_DATA', {...}) saved (see CCSM_Agent5B.gs).
    var payload = loadTempData('A5B_DATA');
    if (!payload) throw new Error('A5B_DATA not found in Script Properties. Did Agent5B run?');
    var qualifying = payload.qualifying || [];
    var weekEnd    = payload.weekEnd    || '';

    var emailsSent  = 0;
    var emailErrors = 0;
    var sentRecords = [];

    qualifying.forEach(function(record) {
      // Collect valid recipient emails
      var emails = [record.email1, record.email2].filter(function(e) {
        if (!e || e.indexOf('@') < 0) return false;
        var lower = e.toLowerCase();
        return lower.indexOf('notreadyyet') < 0 && lower.indexOf('tbd@') < 0;
      });

      if (emails.length === 0) {
        Logger.log('Agent6: No valid emails for ' + record.areaName + ' — skipping');
        return;
      }

      var to      = emails.join(',');
      var subject = a6_buildSubject(record);
      var body    = a6_buildEmail(record, weekEnd);

      try {
        sendEmail(to, subject, body, 'Agent6');
        emailsSent++;
        sentRecords.push({ record: record, to: to, sentAt: new Date() });
        Logger.log('Agent6: Sent to ' + record.areaName + ' (' + to + ') — ' + record.msgId);
      } catch (mailErr) {
        emailErrors++;
        Logger.log('Agent6: Failed for ' + record.areaName + ' — ' + mailErr.message);
      }
    });

    notes.push('Sent: ' + emailsSent + ' | Errors: ' + emailErrors + ' | Qualifying: ' + qualifying.length);

    // Write ENCOURAGEMENT_HISTORY
    a6_writeEncouragementHistory(sentRecords, weekEnd);
    notes.push('ENCOURAGEMENT_HISTORY updated');

    // Send summary to the mission's sending account (no agentName = main account)
    if (qualifying.length > 0 || emailsSent > 0) {
      var summaryTo      = getConfig('SEND_FROM_EMAIL') || 'CCSM.PMG.Compass@gmail.com';
      var summarySubject = a6_buildSummarySubject(emailsSent, qualifying.length, weekEnd);
      var summaryBody    = a6_buildSummaryEmail(sentRecords, qualifying, weekEnd);
      sendEmail(summaryTo, summarySubject, summaryBody);
      notes.push('Summary sent to ' + summaryTo);
    }

    // Clean up Script Properties
    try { saveTempData('A5B_DATA', ''); } catch(e) {}

    Logger.log('Agent6: Complete — ' + notes.join(' | '));

  } catch (e) {
    status = 'ERROR';
    notes.push('ERROR: ' + e.message);
    Logger.log('Agent6 FATAL: ' + e.message + '\n' + (e.stack || ''));
  }

  // logRun(agent, status, recordsProcessed, emailsSent, durationMs, notes, error)
  logRun('Agent6', status, null, null, null, notes.join(' | '));
}

// ─── EMAIL BUILDERS ────────────────────────────────────────────────────────────

/**
 * Subject line — exact template (never varies):
 *   '¡Buen trabajo, ' + areaName + '! 🎉'
 */
function a6_buildSubject(record) {
  return '¡Buen trabajo, ' + record.areaName + '! 🎉';
}

/**
 * Builds the encouragement email body.
 * All narrative text comes from MESSAGE_BANK — nothing is AI-generated.
 * The congratulatory line is the only generated sentence, and it is a fixed
 * template that only interpolates numbers/names, never composes new prose:
 *   '¡Felicitaciones! Esta semana su área alcanzó el ' + pct + '% de su meta de ' + metricDisplay + '.'
 */
function a6_buildEmail(record, weekEnd) {
  var msg       = record.msgObj || {};
  var subject   = a6_esc(msg['Subject_Line']    || '');
  var body      = a6_esc(msg['Body_Text']       || '');
  var pmgRef    = a6_formatPmgRef(msg['PMG_Chapter']); // chapter ref straight from MESSAGE_BANK
  var pmgDesc   = a6_esc(msg['PMG_Description'] || '');
  var scripture = a6_esc(msg['Scripture']       || '');
  var scriptTxt = a6_esc(msg['Scripture_Text']  || '');
  var dateLabel = weekEnd ? a6_formatDate(weekEnd) : 'esta semana';

  var pct           = record.bestMetric ? Math.round(record.bestMetric.pct * 100) : 0;
  var metricDisplay = record.bestMetric ? a6_esc(record.bestMetric.display || record.bestMetric.key) : '';

  var congratsLine = '¡Felicitaciones! Esta semana su área alcanzó el ' + pct +
    '% de su meta de ' + metricDisplay + '.';

  var C = { header: '#1e3a5f', green: '#15803d', muted: '#6b7280', border: '#e5e7eb' };

  var html = '<div style="font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;color:#111;">';

  // Header
  html += '<div style="background:' + C.header + ';color:white;padding:18px 22px;border-radius:8px 8px 0 0;">'
    + '<div style="font-size:17px;font-weight:700;">PMG Compass — Reconocimiento del Viernes</div>'
    + '<div style="font-size:12px;opacity:0.75;margin-top:4px;">Semana que termina el ' + dateLabel + '</div>'
    + '</div>';

  // Congratulatory banner (fixed template — see function doc comment)
  html += '<div style="background:#f0fdf4;border-left:4px solid ' + C.green + ';padding:12px 18px;'
    + 'font-size:13px;color:' + C.green + ';font-weight:600;">'
    + a6_esc(congratsLine)
    + '</div>';

  // Message block
  html += '<div style="padding:20px 22px;">';
  if (subject) {
    html += '<div style="font-size:15px;font-weight:700;color:' + C.header + ';margin-bottom:12px;">'
      + '&ldquo;' + subject + '&rdquo;</div>';
  }
  if (body) {
    html += '<div style="font-size:13px;line-height:1.7;color:#1f2937;">'
      + body.replace(/\n/g, '<br>') + '</div>';
  }

  // PMG + scripture references
  if (pmgRef || scripture) {
    html += '<div style="margin-top:16px;padding:10px 14px;background:#f9fafb;border-radius:6px;'
      + 'font-size:11px;color:' + C.muted + ';">';
    if (pmgRef)    html += '&#128214; <strong>' + a6_esc(pmgRef) + '</strong>'
      + (pmgDesc ? ' &mdash; ' + pmgDesc : '') + '<br>';
    if (scripture) html += '&#9998; ' + scripture;
    if (scriptTxt) html += '<div style="font-style:italic;margin-top:4px;">' + scriptTxt + '</div>';
    html += '</div>';
  }

  html += '</div>';

  // Footer — exact template: 'PMG Compass — ' + getMissionName()
  html += '<div style="padding:12px 16px;background:#f3f4f6;border-radius:0 0 8px 8px;'
    + 'font-size:11px;color:' + C.muted + ';text-align:center;">'
    + a6_esc('PMG Compass — ' + getMissionName())
    + '</div>';

  html += '</div>';
  return html;
}

// ─── ENCOURAGEMENT HISTORY ─────────────────────────────────────────────────────

/**
 * Appends one row per sent email to ENCOURAGEMENT_HISTORY.
 * Schema: Area | Week_Ending | Message_ID | Sent_Timestamp | Email_Sent_To
 * Creates the header row if the tab is empty (ENCOURAGEMENT_HISTORY ships
 * with no header at all — see CcsmData.gs CCSM_TAB_SPECS).
 */
function a6_writeEncouragementHistory(sentRecords, weekEnd) {
  var sheet = getTab('ENCOURAGEMENT_HISTORY');
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['Area', 'Week_Ending', 'Message_ID', 'Sent_Timestamp', 'Email_Sent_To']);
  }

  var tz  = getMissionTimezone();
  var now = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd HH:mm');

  var newRows = sentRecords.map(function(sr) {
    return [sr.record.areaName, weekEnd, sr.record.msgId, now, sr.to];
  });

  if (newRows.length > 0) {
    var startRow = sheet.getLastRow() + 1;
    sheet.getRange(startRow, 1, newRows.length, newRows[0].length).setValues(newRows);
  }
}

// ─── SUMMARY EMAIL ──────────────────────────────────────────────────────────────

function a6_buildSummarySubject(sent, qualifying, weekEnd) {
  var dateLabel = weekEnd ? a6_formatDate(weekEnd) : 'esta semana';
  return '[PMG Compass] Resumen de Reconocimiento del Viernes — ' + sent + ' enviado(s) | ' + dateLabel;
}

/**
 * Builds the plain HTML summary email for SEND_FROM_EMAIL.
 * Shows: total sent, breakdown by metric, list of qualifying areas.
 */
function a6_buildSummaryEmail(sentRecords, qualifying, weekEnd) {
  var dateLabel = weekEnd ? a6_formatDate(weekEnd) : 'esta semana';
  var C = { header: '#1e3a5f', muted: '#6b7280', border: '#e5e7eb', bgLight: '#f9fafb' };

  // Group by metric for the breakdown table
  var byMetric = {};
  sentRecords.forEach(function(sr) {
    var mk = (sr.record.bestMetric && sr.record.bestMetric.display) || sr.record.bestMetric.key || 'Desconocido';
    if (!byMetric[mk]) byMetric[mk] = [];
    byMetric[mk].push(sr.record.areaName);
  });

  var html = '<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;color:#111;">';

  // Header
  html += '<div style="background:' + C.header + ';color:white;padding:18px 22px;border-radius:8px 8px 0 0;">'
    + '<div style="font-size:17px;font-weight:700;">Resumen de Reconocimiento del Viernes</div>'
    + '<div style="font-size:12px;opacity:0.75;margin-top:4px;">Semana que termina el ' + dateLabel + '</div>'
    + '</div>';

  // Totals row
  var notSent = qualifying.length - sentRecords.length;
  html += '<div style="padding:14px 22px;background:' + C.bgLight + ';font-size:13px;">'
    + '<strong>' + sentRecords.length + '</strong> correo(s) de reconocimiento enviado(s)'
    + ' | <strong>' + qualifying.length + '</strong> área(s) calificaron'
    + (notSent > 0 ? ' | <strong>' + notSent + '</strong> omitido(s) (correo no disponible)' : '')
    + '</div>';

  // Metric breakdown
  if (Object.keys(byMetric).length > 0) {
    html += '<div style="padding:16px 22px;">'
      + '<div style="font-size:14px;font-weight:700;color:' + C.header + ';margin-bottom:10px;'
      + 'border-bottom:2px solid ' + C.header + ';padding-bottom:6px;">Desglose por Indicador</div>'
      + '<table style="width:100%;border-collapse:collapse;font-size:12px;">';

    Object.keys(byMetric).sort().forEach(function(metric) {
      var areas = byMetric[metric];
      html += '<tr style="border-bottom:1px solid ' + C.border + ';">'
        + '<td style="padding:8px 10px;font-weight:600;width:30%;vertical-align:top;">'
        + a6_esc(metric) + ' <span style="color:' + C.muted + ';font-weight:400;">(' + areas.length + ')</span></td>'
        + '<td style="padding:8px 10px;color:#374151;">' + areas.map(a6_esc).join(', ') + '</td>'
        + '</tr>';
    });

    html += '</table></div>';
  }

  // Full list
  if (sentRecords.length > 0) {
    html += '<div style="padding:0 22px 16px;">'
      + '<div style="font-size:14px;font-weight:700;color:' + C.header + ';margin-bottom:10px;'
      + 'border-bottom:2px solid ' + C.header + ';padding-bottom:6px;">Todas las Áreas que Calificaron</div>'
      + '<table style="width:100%;border-collapse:collapse;font-size:12px;">'
      + '<tr style="background:' + C.header + ';color:white;">'
      + '<th style="padding:6px 10px;text-align:left;">Área</th>'
      + '<th style="padding:6px 10px;text-align:left;">Zona</th>'
      + '<th style="padding:6px 10px;text-align:left;">Mejor Indicador</th>'
      + '<th style="padding:6px 10px;text-align:center;">% de Meta</th>'
      + '<th style="padding:6px 10px;text-align:left;">ID de Mensaje</th>'
      + '</tr>';

    sentRecords.forEach(function(sr, idx) {
      var r   = sr.record;
      var pct = r.bestMetric ? Math.round(r.bestMetric.pct * 100) + '%' : '—';
      var bg  = idx % 2 === 0 ? '#ffffff' : C.bgLight;
      html += '<tr style="background:' + bg + ';">'
        + '<td style="padding:6px 10px;">' + a6_esc(r.areaName) + '</td>'
        + '<td style="padding:6px 10px;color:' + C.muted + ';">' + a6_esc(r.zone) + '</td>'
        + '<td style="padding:6px 10px;">' + a6_esc((r.bestMetric && r.bestMetric.display) || r.bestMetric.key) + '</td>'
        + '<td style="padding:6px 10px;text-align:center;font-weight:600;color:#15803d;">' + pct + '</td>'
        + '<td style="padding:6px 10px;font-family:monospace;font-size:11px;">' + a6_esc(r.msgId) + '</td>'
        + '</tr>';
    });

    html += '</table></div>';
  }

  // Footer
  html += '<div style="padding:12px 16px;background:' + C.bgLight + ';border-radius:0 0 8px 8px;'
    + 'font-size:11px;color:' + C.muted + ';text-align:center;">'
    + a6_esc('PMG Compass Agent6 — ' + getMissionName()) + '</div>';

  html += '</div>';
  return html;
}

// ─── UTILITIES ────────────────────────────────────────────────────────────────

function a6_esc(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/**
 * Formats the Predicad Mi Evangelio (Preach My Gospel) reference straight
 * from the MESSAGE_BANK PMG_Chapter value — displays the stored chapter
 * AS-IS under the "Predicad Mi Evangelio" label, never forcing a "p." page
 * prefix. Mirrors a1c_formatPmgRef (CCSM_Agent1C.gs) so this fork uses the
 * same Spanish title throughout. Returns '' when the cell is empty.
 */
function a6_formatPmgRef(raw) {
  var v = String(raw || '').trim();
  if (!v) return '';
  if (/predicad mi evangelio/i.test(v)) return v;
  v = v.replace(/^pmg\b[\s.,:–—-]*/i, '');
  return 'Predicad Mi Evangelio, ' + v;
}

// Fixed Spanish month names — Utilities.formatDate's 'MMMM' token does NOT
// localize under GAS/Java's default locale (renders English regardless of
// script locale; same finding documented in CCSM_Agent1C.gs A1C_SPANISH_MONTHS).
var A6_SPANISH_MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

function a6_formatDate(dateStr) {
  try {
    var p  = String(dateStr).split('-');
    var d  = new Date(parseInt(p[0], 10), parseInt(p[1], 10) - 1, parseInt(p[2], 10), 12);
    var tz = getMissionTimezone();
    var day   = Utilities.formatDate(d, tz, 'd');
    var year  = Utilities.formatDate(d, tz, 'yyyy');
    var month = parseInt(Utilities.formatDate(d, tz, 'M'), 10);
    return day + ' de ' + (A6_SPANISH_MONTHS[month - 1] || '') + ' de ' + year;
  } catch(e) { return dateStr; }
}
