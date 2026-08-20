/**
 * ============================================================
 * CCSM_AgentValidation.gs — Data Validation Agent
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of AgentValidation.gs (docs/AgentValidation.gs in PMG-Compass).
 * Internal av_* function names are kept identical to the Provo original so
 * future diffs stay readable.
 *
 * Runs BEFORE duplicate detection in onNightlyFormSubmit (CCSM_AgentDuplicate.gs).
 * If any numeric field on the just-submitted row contains an invalid value,
 * it:
 *   1. Sets STATUS = 'VALIDATION_ERROR' on the row
 *   2. Emails the area missionaries (Spanish) with the specific field(s) that
 *      failed
 *   3. Logs to AUDIT_LOG
 *   4. Returns false — caller must skip duplicate detection for this row
 *
 * STRUCTURAL CHANGE vs Provo: the Provo original was a flat single-section
 * form with per-companion column SUFFIXES (' ', ' 2', ' 3'). CCSM's Google
 * Forms are split into one repeated section PER ZONE (see
 * CCSM_Agent3.gs's a3_parseSectionStructure / CCSM_FORM_STRUCTURAL) — a
 * single companionship fills exactly one section, not per-companion
 * suffixed columns — so av_validateFormRow locates the FILLED section (via
 * the area column) and validates the numeric fields within it, instead of
 * scanning fixed suffix variants.
 *
 * Numeric field lists are read directly from CCSM_NIGHTLY_QUESTIONS /
 * CCSM_WEEKLY_QUESTIONS (CcsmData.gs) — the same single source of truth the
 * live forms and every other CCSM agent use — rather than a hardcoded
 * literal list, so this file can never drift out of sync with the form.
 *
 * INTEGRATION: CCSM_AgentDuplicate.gs's onNightlyFormSubmit() calls
 * av_validateFormRow(e, 'nightly') first and returns early if it is false.
 */

// ── Numeric fields — derived from the single source of truth in CcsmData.gs ───
// FUNCTIONS, not top-level vars: Apps Script concatenates every .gs file's
// top-level code into one script and does not guarantee CcsmData.gs runs
// before this file, so evaluating these eagerly at load time could hit
// CCSM_NIGHTLY_QUESTIONS/CCSM_WEEKLY_QUESTIONS before they exist (same class
// of TypeError confirmed live 2026-08-20 in CCSM_AgentScores.gs's analogous
// top-level ASC_KI_WEIGHTS). Computing lazily on first call sidesteps
// file-load order entirely.
function av_nightlyNumericFields() {
  return CCSM_NIGHTLY_QUESTIONS
    .filter(function(q) { return q.type === 'NUMBER'; })
    .map(function(q) { return q.headerEs; });
}

function av_weeklyNumericFields() {
  return CCSM_WEEKLY_QUESTIONS
    .filter(function(q) { return q.type === 'NUMBER'; })
    .map(function(q) { return q.headerEs; });
}


/**
 * Main entry point called from onNightlyFormSubmit (and, if a weekly-form
 * trigger is ever added, onWeeklyFormSubmit).
 * Returns true if validation passed (proceed to duplicate check).
 * Returns false if validation failed (skip duplicate check for this row).
 *
 * @param {Object} e - Apps Script form submit event object (unused — CCSM's
 *   raw tabs are read directly, matching CCSM_AgentDuplicate.gs's own
 *   convention; kept for API compatibility with the real onFormSubmit trigger).
 * @param {string} formType - 'nightly' or 'weekly'
 * @returns {boolean}
 */
function av_validateFormRow(e, formType) {
  try {
    var tabName = formType === 'weekly' ? 'WEEKLY_FORM_RAW' : 'NIGHTLY_FORM_RAW';
    var rawData = av_getSheetData(tabName);
    if (!rawData || rawData.length < 2) return true; // nothing to validate

    var headers    = rawData[0].map(function(h) { return String(h).trim(); });
    var lastRowIdx = rawData.length - 1; // 0-based index into rawData
    var lastRow    = rawData[lastRowIdx];

    // ── Locate the filled zone-section (one area column per zone) ─────────────
    var areaTarget = CCSM_FORM_STRUCTURAL.areaCol;
    var areaCols   = [];
    headers.forEach(function(h, idx) { if (h === areaTarget) areaCols.push(idx); });
    if (areaCols.length === 0) return true; // structurally unrecognized — don't block

    var sectionStart = -1;
    for (var s = 0; s < areaCols.length; s++) {
      if (String(lastRow[areaCols[s]] || '').trim()) { sectionStart = areaCols[s]; break; }
    }
    if (sectionStart === -1) return true; // no section filled — nothing to validate

    var idxInAreaCols = areaCols.indexOf(sectionStart);
    var sectionEnd    = (idxInAreaCols + 1 < areaCols.length) ? areaCols[idxInAreaCols + 1] : headers.length;

    // ── Validate every numeric field found within that section ────────────────
    var numericFields = formType === 'weekly' ? av_weeklyNumericFields() : av_nightlyNumericFields();
    var failures = []; // { field, value }

    numericFields.forEach(function(fieldName) {
      var colIdx = -1;
      for (var i = sectionStart; i < sectionEnd; i++) {
        if (headers[i] === fieldName) { colIdx = i; break; }
      }
      if (colIdx === -1) return; // column not present in this section — skip

      var raw = lastRow[colIdx];
      if (raw === '' || raw === null || raw === undefined) return; // blank is OK

      var strVal = String(raw).trim();
      if (!av_isNonNegativeInteger(strVal)) {
        failures.push({ field: fieldName, value: strVal });
      }
    });

    if (failures.length === 0) return true; // all good

    // ── Validation failed — mark row, email missionaries, log ─────────────────
    av_markRowStatus(tabName, headers, lastRowIdx + 1, 'VALIDATION_ERROR'); // +1 for sheet 1-based row

    var areaName   = String(lastRow[sectionStart] || '').trim();
    var dateStr    = av_getDateField(headers, lastRow, sectionStart, sectionEnd);
    var missionOrg = av_loadMissionOrg();
    var emails     = av_getMissionaryEmails(areaName, missionOrg);
    var formLink   = getConfig(formType === 'weekly' ? 'WEEKLY_FORM_LINK' : 'NIGHTLY_FORM_LINK') || '';

    if (emails.length > 0 && MailApp.getRemainingDailyQuota() >= 20) {
      var subject = 'Por favor, reenvíe su informe — se detectó un valor no válido';
      var body    = av_buildValidationEmail(areaName, dateStr, failures, formLink);
      emails.forEach(function(email) {
        sendEmail(email, subject, body, 'AgentValidation');
      });
    } else if (emails.length === 0) {
      Logger.log('AgentValidation: No emails found for area: ' + areaName);
    } else {
      Logger.log('AgentValidation: Quota too low — skipped email for ' + areaName);
    }

    av_logAudit('VALIDATION_ERROR', lastRowIdx + 1, areaName,
      failures.length + ' field(s) failed: ' + failures.map(function(f) { return f.field; }).join(', '));

    return false; // skip duplicate detection

  } catch (err) {
    av_logAudit('ERROR', -1, '', err.message);
    Logger.log('AgentValidation ERROR: ' + err.message);
    return true; // on unexpected error, don't block the trigger
  }
}


// ── Helpers ───────────────────────────────────────────────────────────────────

function av_isNonNegativeInteger(val) {
  // Must be a whole number >= 0. Rejects decimals, letters, negatives, 'O' (letter O).
  return /^\d+$/.test(val);
}

function av_getSheetData(tabName) {
  var sheet = getTab(tabName);
  if (!sheet || sheet.getLastRow() === 0) return null;
  return sheet.getDataRange().getValues();
}

/**
 * Reads the report-date field within the filled section and normalizes it
 * to 'YYYY-MM-DD'. Falls back to the raw string if it isn't a parseable date.
 */
function av_getDateField(headers, row, sectionStart, sectionEnd) {
  var dateTarget = CCSM_FORM_STRUCTURAL.dateCol;
  var colIdx = -1;
  for (var i = sectionStart; i < sectionEnd; i++) {
    if (headers[i] === dateTarget) { colIdx = i; break; }
  }
  if (colIdx === -1) return '';
  var raw = row[colIdx];
  if (!raw) return '';
  try {
    return Utilities.formatDate(new Date(raw), getMissionTimezone(), 'yyyy-MM-dd');
  } catch (e) {
    return String(raw);
  }
}

function av_loadMissionOrg() {
  var data = av_getSheetData('MISSION_ORG');
  if (!data || data.length < 2) return [];
  return data;
}

function av_getMissionaryEmails(areaName, missionOrg) {
  if (!missionOrg || missionOrg.length < 2 || !areaName) return [];
  var headers   = missionOrg[0].map(function(h) { return String(h).trim(); });
  var areaCol   = headers.indexOf('Area_Name');
  var email1Col = headers.indexOf('Companion1_Email');
  var email2Col = headers.indexOf('Companion2_Email');
  if (areaCol === -1) return [];

  var emails = [];
  var canon  = areaName.trim().toLowerCase();
  for (var i = 1; i < missionOrg.length; i++) {
    var row = missionOrg[i];
    if (String(row[areaCol]).trim().toLowerCase() !== canon) continue;
    var e1 = email1Col !== -1 ? String(row[email1Col]).trim() : '';
    var e2 = email2Col !== -1 ? String(row[email2Col]).trim() : '';
    // NOTE (fixed vs the Provo original): 'tbd'/'@notreadyyet.com' are
    // substring markers to reject — they must NOT include '' in that list,
    // since indexOf('')/includes('') is always 0/true for ANY string,
    // which silently made the Provo original's equivalent guard permanently
    // reject every email (av_getMissionaryEmails always returned []). The
    // blank check is already covered by the `e1 &&` / `e2 &&` guards below.
    var invalidSubstrings = ['tbd', '@notreadyyet.com'];
    if (e1 && !invalidSubstrings.some(function(s) { return e1.toLowerCase().indexOf(s) !== -1; })) emails.push(e1);
    if (e2 && !invalidSubstrings.some(function(s) { return e2.toLowerCase().indexOf(s) !== -1; })) emails.push(e2);
    break;
  }
  return emails;
}

function av_markRowStatus(tabName, headers, sheetRowNumber, status) {
  var sheet = getTab(tabName);
  if (!sheet) return;

  var statusCol = headers.indexOf('STATUS');
  if (statusCol === -1) {
    // Append STATUS column header
    var lastCol = headers.length + 1;
    sheet.getRange(1, lastCol).setValue('STATUS');
    statusCol = lastCol - 1; // 0-based
  }
  sheet.getRange(sheetRowNumber, statusCol + 1).setValue(status);
}

function av_buildValidationEmail(areaName, dateStr, failures, formLink) {
  var lines = [];
  lines.push('<p>Estimados misioneros de <strong>' + areaName + '</strong>,</p>');
  lines.push('<p>Notamos un problema con su informe enviado para <strong>' + (dateStr || 'la fecha que ingresó') + '</strong>. ');
  lines.push('Uno o más campos contenían un valor que no es un número entero válido (como 0, 1, 2, etc.).</p>');
  lines.push('<p><strong>Campos que necesitan corrección:</strong></p>');
  lines.push('<table style="border-collapse:collapse;font-size:14px;">');
  lines.push('<tr style="background:#f3f4f6;"><th style="padding:8px 12px;text-align:left;border:1px solid #d1d5db;">Campo</th>');
  lines.push('<th style="padding:8px 12px;text-align:left;border:1px solid #d1d5db;">Lo que Ingresó</th></tr>');
  failures.forEach(function(f) {
    lines.push('<tr><td style="padding:8px 12px;border:1px solid #d1d5db;">' + f.field + '</td>');
    lines.push('<td style="padding:8px 12px;border:1px solid #d1d5db;">' + f.value + '</td></tr>');
  });
  lines.push('</table>');
  lines.push('<p>Por favor, reenvíe su informe con los valores corregidos usando el enlace a continuación.</p>');
  if (formLink) {
    lines.push('<p><a href="' + formLink + '">Reenviar su Informe</a></p>');
  }
  lines.push('<p>Gracias por su diligencia y el gran trabajo que están haciendo. ¡Estamos agradecidos por ustedes!</p>');
  lines.push('<p style="color:#6b7280;font-size:12px;">— Sistema PMG Compass (' + getMissionName() + ')</p>');
  return lines.join('\n');
}

function av_logAudit(action, rowNumber, area, notes) {
  try {
    var sheet = getTab('AUDIT_LOG');
    if (!sheet) return;
    if (sheet.getLastColumn() === 0 || sheet.getLastRow() === 0) {
      sheet.appendRow(['Timestamp', 'Agent', 'Action', 'Rows_Affected', 'Area', 'Notes']);
    }
    sheet.appendRow([
      Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd HH:mm:ss'),
      'AgentValidation',
      action,
      rowNumber,
      area,
      notes
    ]);
  } catch (e) {
    Logger.log('av_logAudit failed: ' + e.message);
  }
}
