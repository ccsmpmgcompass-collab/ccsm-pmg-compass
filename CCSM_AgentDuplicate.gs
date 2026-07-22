/**
 * ============================================================
 * CCSM_AgentDuplicate.gs — Duplicate Submission Detector
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of AgentDuplicate.gs (docs/AgentDuplicate.gs in PMG-Compass). Internal
 * ad_* function names are kept identical to the Provo original so future
 * diffs stay readable; only the form column constants (Spanish CCSM form
 * text), the duplicate-notification email (Spanish), the form link (read
 * from AGENT_CONFIG instead of a hardcoded Provo form URL), the timestamp
 * column lookup ("Marca temporal" — see CCSM_Agent5A.gs's same note), and
 * the timezone source are changed.
 *
 * NOTE: onNightlyFormSubmit() is gated behind av_validateFormRow(e, 'nightly')
 * (CCSM_AgentValidation.gs, Task 12) — an invalid numeric field on the
 * just-submitted row is flagged VALIDATION_ERROR and emailed back to the
 * missionaries BEFORE the duplicate scan runs, and duplicate detection is
 * skipped for that submission. `e` is accepted for API compatibility with
 * the real onFormSubmit trigger but otherwise unused.
 *
 * SCHEDULE: Fires automatically on every nightly form submission.
 *           Run setupAgentDuplicateTrigger() ONCE to install the trigger.
 *
 * WHAT IT DOES:
 *   1. Reads the new submission's area name and date from NIGHTLY_FORM_RAW
 *   2. Scans the rest of NIGHTLY_FORM_RAW for another row with the same area + date
 *   3. If a duplicate is found:
 *      a. Emails both missionaries (from MISSION_ORG) with an HTML summary of both submissions
 *      b. Deletes ALL rows for that area+date from NIGHTLY_FORM_RAW
 *      c. Logs the event per-group to AUDIT_LOG (via ad_logAudit — same
 *         Timestamp | Agent | Action | Rows_Affected | Area | Notes layout the
 *         other CCSM agents use), and the whole run to AGENT_RUN_LOG (via
 *         logRun — see CCSM_Helpers.gs). AGENT_RUN_LOG records THAT a run
 *         happened; AUDIT_LOG records WHICH rows it flagged, which is what
 *         answers "why does this area show 16 contacts instead of 8?".
 */

// --- FORM COLUMN CONSTANTS ---
// Must match the exact question text in the CCSM Spanish Google Form
// (DailyReportForm_ES.gs / CcsmData.gs CCSM_FORM_STRUCTURAL) — same
// constants CCSM_Agent3.gs uses (A3_FORM_AREA_COL / A3_FORM_DATE_COL /
// A3_FORM_ZONE_COL), kept as separate ad_-scoped constants here so this file
// stays self-contained like the Provo original.
var AD_FORM_AREA_COL = '¿En qué área sirve?';
var AD_FORM_DATE_COL = '¿Qué fecha está ingresando?';
var AD_FORM_ZONE_COL = '¿En qué zona sirve?';

// --- MAIN ENTRY POINT ---

function onNightlyFormSubmit(e) {
  var status = 'SUCCESS';
  var notes  = [];

  try {
    Logger.log('AgentDuplicate: Form submit received - ' + new Date().toISOString());

    // Phase 4 (CCSM_AgentValidation.gs): validate first — skip duplicate
    // detection entirely for a row that already failed validation.
    var isValid = av_validateFormRow(e, 'nightly');
    if (!isValid) {
      Logger.log('AgentDuplicate: row failed validation — skipping duplicate check.');
      return;
    }

    var rawData = ad_getSheetData('NIGHTLY_FORM_RAW');
    if (!rawData || rawData.length < 2) {
      Logger.log('AgentDuplicate: NIGHTLY_FORM_RAW has no data rows - nothing to check.');
      return;
    }

    var headers    = rawData[0].map(function(h) { return String(h).trim(); });
    var missionOrg = ad_loadMissionOrg();
    var areaLookup = ad_buildAreaLookup(missionOrg);
    var parsedRows = ad_parseAllRows(rawData, headers, areaLookup);

    var groups = {};
    parsedRows.forEach(function(p) {
      if (!p.canonArea || !p.dateStr) return;
      var key = p.canonArea + '|' + p.dateStr;
      if (!groups[key]) groups[key] = [];
      groups[key].push(p);
    });

    var duplicatesFound = 0;

    Object.keys(groups).forEach(function(key) {
      var group = groups[key];
      if (group.length < 2) return;

      duplicatesFound++;
      var canonArea = group[0].canonArea;
      var dateStr   = group[0].dateStr;

      Logger.log('AgentDuplicate: Duplicate detected - ' + canonArea + ' / ' + dateStr +
                 ' (' + group.length + ' rows)');

      var email = ad_getMissionaryEmail(canonArea, missionOrg);
      if (!email) {
        notes.push('No email found for ' + canonArea + ' - skipped notification');
        Logger.log('AgentDuplicate: No email found for area: ' + canonArea);
      } else {
        // Timestamp is always column A ("Marca temporal") for CCSM's Spanish
        // Google Forms responses — read positionally rather than by header
        // name, matching the convention already used in CCSM_Agent5A.gs /
        // CCSM_AgentEscalation.gs for the same column.
        var tsIdx = 0;

        var submissions = group.map(function(p) {
          var ts = p.rawRow[tsIdx] ? String(p.rawRow[tsIdx]) : 'Desconocido';
          return { timestamp: ts, fields: ad_extractFields(p.rawRow, headers) };
        });

        var subject = 'Envío Duplicado del Formulario — ' + canonArea + ' — ' + dateStr;
        var body    = ad_buildDuplicateEmailBody(canonArea, dateStr, submissions);
        sendEmail(email, subject, body, 'AgentDuplicate');
        notes.push('Email sent to ' + email + ' for ' + canonArea + ' (' + dateStr + ')');
        Logger.log('AgentDuplicate: Email sent to ' + email);
      }

      var rowIndicesToDelete = group.map(function(p) { return p.rowIndex; });
      rowIndicesToDelete.sort(function(a, b) { return b - a; });
      var sheet = getTab('NIGHTLY_FORM_RAW');
      rowIndicesToDelete.forEach(function(idx) {
        sheet.deleteRow(idx);
        Logger.log('AgentDuplicate: Deleted row ' + idx + ' from NIGHTLY_FORM_RAW');
      });

      notes.push('Deleted ' + rowIndicesToDelete.length + ' row(s) for ' + canonArea + ' / ' + dateStr);

      // Per-EVENT trail. logRun() below records that the sweep ran; only this
      // records which area/date was flagged and how many raw rows went with it.
      ad_logAudit(
        'DUPLICATE_RESOLVED',
        rowIndicesToDelete.length,
        canonArea,
        dateStr + ' — ' + group.length + ' submission(s) removed from NIGHTLY_FORM_RAW; ' +
        (email ? 'notified ' + email : 'no email on file for this area')
      );
    });

    if (duplicatesFound === 0) {
      Logger.log('AgentDuplicate: No duplicates found - clean submission.');
      notes.push('No duplicates found');
    } else {
      notes.push(duplicatesFound + ' duplicate group(s) resolved');
    }

  } catch (err) {
    status = 'ERROR';
    notes.push('ERROR: ' + err.message);
    Logger.log('AgentDuplicate FATAL: ' + err.message + '\n' + (err.stack || ''));
  }

  // logRun(agent, status, recordsProcessed, emailsSent, durationMs, notes, error)
  logRun('AgentDuplicate', status, null, null, null, notes.join(' | '));
}

// --- AUDIT LOG ---

/**
 * Appends one row to AUDIT_LOG, in the layout every other CCSM agent uses:
 * Timestamp | Agent | Action | Rows_Affected | Area | Notes
 * (cf. ar_logAudit, av_logAudit, ae_logAudit, aqa_logAudit).
 *
 * AUDIT_LOG ships headerless (CcsmData.gs CCSM_TAB_SPECS), so the header row
 * is bootstrapped on first write — same as CCSM_AgentReminder.gs does.
 * Never throws: a failed audit write must not abort the duplicate sweep.
 */
function ad_logAudit(action, rowsAffected, area, notes) {
  try {
    var sheet = getTab('AUDIT_LOG');
    if (!sheet) return;

    if (sheet.getLastColumn() === 0 || sheet.getLastRow() === 0) {
      sheet.appendRow(['Timestamp', 'Agent', 'Action', 'Rows_Affected', 'Area', 'Notes']);
    }

    sheet.appendRow([
      Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd HH:mm:ss'),
      'AgentDuplicate',
      action,
      rowsAffected,
      area  || '',
      notes || ''
    ]);
  } catch (e) {
    Logger.log('AgentDuplicate: audit log write failed — ' + e.message);
  }
}


// --- DATA LOADERS ---

function ad_getSheetData(tabName) {
  var sheet = getTab(tabName);
  if (!sheet || sheet.getLastRow() === 0) return [];
  return sheet.getDataRange().getValues();
}

function ad_loadMissionOrg() {
  var data = ad_getSheetData('MISSION_ORG');
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

  return areas;
}

function ad_buildAreaLookup(missionOrg) {
  var lookup = {};
  missionOrg.forEach(function(a) {
    if (a['Area_Name']) lookup[a['Area_Name'].toLowerCase()] = a['Area_Name'];
  });
  return lookup;
}

// --- PARSING ---
//
// The CCSM nightly form is multi-section — one "¿En qué área sirve?" /
// "¿Qué fecha está ingresando?" pair repeats once per zone (see
// CCSM_Agent3.gs a3_parseSectionStructure for the same structure). This
// mirrors that section-detection approach: locate every area-column
// occurrence, use the first section as the offset template, then find which
// section a given row filled by locating its non-blank area column.

function ad_parseAllRows(rawData, headers, areaLookup) {
  var areaTarget = AD_FORM_AREA_COL.toLowerCase();
  var dateTarget = AD_FORM_DATE_COL.toLowerCase();

  var areaCols = [];
  headers.forEach(function(h, idx) {
    if (h.toLowerCase() === areaTarget) areaCols.push(idx);
  });
  if (areaCols.length === 0) {
    Logger.log('AgentDuplicate: No area column found in NIGHTLY_FORM_RAW');
    return [];
  }

  var sectionStart = areaCols[0];
  var sectionEnd   = areaCols.length > 1 ? areaCols[1] : headers.length;
  var dateOffset   = -1;
  for (var j = sectionStart; j < sectionEnd; j++) {
    if (headers[j].toLowerCase() === dateTarget) {
      dateOffset = j - sectionStart;
      break;
    }
  }
  if (dateOffset < 0) {
    Logger.log('AgentDuplicate: No date column found in section');
    return [];
  }

  var result = [];

  for (var i = 1; i < rawData.length; i++) {
    var row         = rawData[i];
    var sheetRowIdx = i + 1;

    var filledStart = -1;
    var rawArea     = '';
    for (var s = 0; s < areaCols.length; s++) {
      var val = String(row[areaCols[s]] || '').trim();
      if (val) { filledStart = areaCols[s]; rawArea = val; break; }
    }

    var canonArea = rawArea ? (areaLookup[rawArea.toLowerCase()] || null) : null;
    var dateStr   = null;
    if (filledStart >= 0) {
      dateStr = ad_toDateString(row[filledStart + dateOffset]);
    }

    result.push({
      rowIndex:  sheetRowIdx,
      canonArea: canonArea,
      dateStr:   dateStr,
      rawArea:   rawArea,
      rawRow:    row
    });
  }

  return result;
}

// --- EMAIL ---

function ad_getMissionaryEmail(canonArea, missionOrg) {
  for (var i = 0; i < missionOrg.length; i++) {
    var a = missionOrg[i];
    if (a['Area_Name'] !== canonArea) continue;

    var emails = [a['Companion1_Email'], a['Companion2_Email']].filter(function(e) {
      if (!e || !e.trim()) return false;
      var lower = e.toLowerCase();
      return lower.indexOf('notreadyyet') < 0 && lower.indexOf('tbd@') < 0;
    });

    if (emails.length > 0) return emails.join(',');
  }
  return '';
}

function ad_buildDuplicateEmailBody(areaName, dateStr, submissions) {
  var FORM_URL = getConfig('NIGHTLY_FORM_LINK') || '';

  var cards = '';
  for (var i = 0; i < submissions.length; i++) {
    var sub  = submissions[i];
    var trs  = '';
    for (var r = 0; r < sub.fields.length; r++) {
      var f   = sub.fields[r];
      var lbl = f.label;
      var val = f.value;
      trs += '<tr>';
      trs += '<td style="padding:5px 16px 5px 0;color:#6b7280;font-size:13px;vertical-align:top;white-space:nowrap;">' + lbl + '</td>';
      trs += '<td style="padding:5px 0;font-size:13px;font-weight:600;color:#111827;">' + val + '</td>';
      trs += '</tr>';
    }
    var num = i + 1;
    var ts  = sub.timestamp;
    cards += '<div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px;margin-bottom:16px;">';
    cards += '<div style="font-size:14px;font-weight:700;color:#003087;margin-bottom:4px;">Envío ' + num + '</div>';
    cards += '<div style="font-size:12px;color:#9ca3af;margin-bottom:12px;">Recibido: ' + ts + '</div>';
    cards += '<table style="border-collapse:collapse;width:100%;">' + trs + '</table>';
    cards += '</div>';
  }

  var html = '';
  html += '<div style="font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;background:#f3f4f6;padding:24px;">';
  html += '<div style="background:#003087;color:#ffffff;padding:16px 24px;border-radius:8px 8px 0 0;">';
  html += '<div style="font-size:16px;font-weight:700;">PMG Compass</div>';
  html += '<div style="font-size:12px;opacity:0.8;margin-top:2px;">' + (getMissionName() || 'Mission') + '</div>';
  html += '</div>';
  html += '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px;padding:24px;">';
  html += '<p style="margin:0 0 12px;font-size:15px;color:#111827;">Hola <strong>' + areaName + '</strong>,</p>';
  html += '<p style="margin:0 0 20px;font-size:14px;color:#374151;line-height:1.6;">';
  html += 'Notamos que el formulario nocturno fue enviado <strong>más de una vez</strong> para ';
  html += '<strong>' + areaName + '</strong> el <strong>' + dateStr + '</strong>. ';
  html += 'Para mantener sus números exactos, hemos eliminado ambos envíos para que pueda volver a enviarlo con la información correcta.';
  html += '</p>';
  html += '<div style="font-size:13px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:12px;">Lo Que Recibimos</div>';
  html += cards;
  html += '<hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;">';
  html += '<div style="text-align:center;padding:20px;background:#eff6ff;border-radius:8px;margin-bottom:20px;">';
  html += '<div style="font-size:14px;font-weight:600;color:#1e3a8a;margin-bottom:14px;">Por favor, vuelva a enviarlo una sola vez con los datos correctos para ' + dateStr + '</div>';
  if (FORM_URL) {
    html += '<a href="' + FORM_URL + '" style="display:inline-block;background:#003087;color:#ffffff;padding:10px 24px;border-radius:6px;text-decoration:none;font-size:14px;font-weight:600;">Reenviar Formulario Nocturno</a>';
  }
  html += '</div>';
  html += '<p style="margin:0 0 6px;font-size:13px;color:#6b7280;">Si tiene alguna pregunta, comuníquese con su líder de distrito o de zona.</p>';
  html += '<p style="margin:0 0 16px;font-size:13px;color:#6b7280;">¡Gracias por su trabajo y por asegurarse de que sus números sean exactos!</p>';
  html += '<p style="margin:0;font-size:13px;color:#374151;font-weight:600;">-- PMG Compass</p>';
  html += '</div>';
  html += '</div>';
  return html;
}

function ad_extractFields(row, headers) {
  var SKIP = ['Marca temporal', AD_FORM_ZONE_COL, AD_FORM_AREA_COL];
  var result = [];
  for (var i = 0; i < headers.length; i++) {
    var label = String(headers[i]).trim();
    var value = row[i];
    if (SKIP.indexOf(label) !== -1) continue;
    if (value === '' || value === null || value === undefined) continue;
    result.push({ label: label, value: String(value) });
  }
  return result;
}

// --- UTILITIES ---

function ad_toDateString(val) {
  if (val === null || val === undefined || val === '') return null;
  var d;
  if (val instanceof Date) {
    d = val;
  } else if (typeof val === 'number') {
    d = new Date(Date.UTC(1899, 11, 30) + val * 86400000);
  } else {
    var s = String(val).trim();
    // yyyy-MM-dd strings are taken literally — new Date('yyyy-MM-dd') parses
    // as UTC midnight, which is the PREVIOUS day in the mission's timezone.
    var m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return m[1] + '-' + m[2] + '-' + m[3];
    d = new Date(s);
  }
  if (isNaN(d.getTime())) return null;
  return Utilities.formatDate(d, getMissionTimezone(), 'yyyy-MM-dd');
}

// --- TRIGGER SETUP ---

function setupAgentDuplicateTrigger() {
  deleteTriggerByName('onNightlyFormSubmit');

  ScriptApp.newTrigger('onNightlyFormSubmit')
    .forSpreadsheet(SpreadsheetApp.getActiveSpreadsheet())
    .onFormSubmit()
    .create();

  Logger.log('AgentDuplicate trigger created: onNightlyFormSubmit on form submit');
}

function testAgentDuplicate() {
  Logger.log('=== AgentDuplicate TEST MODE ===');

  var rawData = ad_getSheetData('NIGHTLY_FORM_RAW');
  if (!rawData || rawData.length < 2) {
    Logger.log('TEST: NIGHTLY_FORM_RAW is empty - nothing to check');
    return;
  }

  var headers    = rawData[0].map(function(h) { return String(h).trim(); });
  var missionOrg = ad_loadMissionOrg();
  var areaLookup = ad_buildAreaLookup(missionOrg);
  var parsedRows = ad_parseAllRows(rawData, headers, areaLookup);

  Logger.log('TEST: Parsed ' + parsedRows.length + ' data rows');

  var groups = {};
  parsedRows.forEach(function(p) {
    if (!p.canonArea || !p.dateStr) return;
    var key = p.canonArea + '|' + p.dateStr;
    if (!groups[key]) groups[key] = [];
    groups[key].push(p);
  });

  var dupeCount = 0;
  Object.keys(groups).forEach(function(key) {
    if (groups[key].length >= 2) {
      dupeCount++;
      var g = groups[key][0];
      Logger.log('TEST: DUPLICATE FOUND - Area: ' + g.canonArea + ' | Date: ' + g.dateStr +
                 ' | ' + groups[key].length + ' rows at sheet rows: ' +
                 groups[key].map(function(p) { return p.rowIndex; }).join(', '));
      var email = ad_getMissionaryEmail(g.canonArea, missionOrg);
      Logger.log('TEST: Would email: ' + (email || '(no email on file)'));
    }
  });

  if (dupeCount === 0) Logger.log('TEST: No duplicates found in current NIGHTLY_FORM_RAW');
  Logger.log('=== TEST COMPLETE ===');
}
