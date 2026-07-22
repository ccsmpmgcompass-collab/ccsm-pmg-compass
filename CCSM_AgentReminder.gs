/**
 * ============================================================
 * CCSM_AgentReminder.gs — Notes + Weekly Compliance Reminder Agent
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of AgentReminder.gs (docs/AgentReminder.gs in PMG-Compass). Internal
 * ar_* function names are kept identical to the Provo original so future
 * diffs stay readable. Two independent halves, same as the Provo original:
 *
 *   1. NOTES reminders — scans the NOTES tab hourly and sends reminder
 *      emails to note authors when their Reminder_DateTime falls within the
 *      next 6 hours (mission timezone). Schema/logic unchanged from Provo;
 *      only the email text is translated to Spanish and the timezone
 *      literal is replaced.
 *   2. Weekly form compliance reminders — finds active areas that have not
 *      submitted WEEKLY_FORM_RAW since last Sunday and sends a Spanish
 *      reminder. Restores the Provo original's Monday/Tuesday 8 AM–9 PM
 *      (mission timezone) day/hour gate — see "Weekly compliance time gate"
 *      below.
 *
 * Weekly compliance time gate (restored from Provo, code review finding):
 * ar_checkWeeklyCompliance() only sends on Monday or Tuesday, between 8 AM
 * and 9 PM (mission timezone). Without this gate, an hourly trigger (see
 * setupReminderTrigger()) would fire the weekly reminder at any hour of any
 * day once Task 14 wires up triggers — including 3 AM. The once-per-week
 * PropertiesService dedup and SYSTEM_START_DATE guard are unchanged, so
 * areas are still reminded at most once per week regardless.
 * TEST BYPASS: runReminderAgent(opts) accepts an optional opts object;
 * opts.skipTimeGate === true skips ONLY the day/hour gate (not the
 * SYSTEM_START_DATE guard or the once-per-week dedup), so automated tests
 * can run deterministically on any day/hour. Production trigger calls
 * runReminderAgent() with no arguments, so the gate is always active there.
 * OPERATIONAL NOTE (mirrors the Provo original's own comment): if
 * CCSM_AgentEscalation.gs's weekly System 2 is also enabled, both agents
 * will independently remind non-submitting areas — pick one mechanism in
 * production, same caution the Provo original calls out. Task 14 turned that
 * caution into an enforced single-owner gate: AGENT_CONFIG's
 * WEEKLY_REMINDER_OWNER selects the owner, and ar_checkWeeklyCompliance()
 * returns 0 immediately unless it is the owner. The SHIPPED DEFAULT is
 * AGENT_ESCALATION, so this half is OFF out of the box. See CCSM_Setup.gs's
 * header for the full deployment decision and why.
 *
 * Gmail quota guard (restored from Provo, code review finding): CCSM's
 * sendEmail() (CCSM_Helpers.gs) never routes AgentReminder traffic through a
 * relay — only Agent1C/Agent3/Agent6/AgentEscalation/AgentReferral do — so
 * every email this agent sends goes straight through MailApp.sendEmail()
 * against the main account's daily Gmail quota. Both halves of this agent
 * (the NOTES loop and ar_checkWeeklyCompliance's MISSION_ORG loop) check
 * MailApp.getRemainingDailyQuota() before every send and stop cleanly (no
 * thrown exception) once it drops below 20, logging QUOTA_LOW to AUDIT_LOG.
 * Progress already made before the guard trips is never lost: the NOTES loop
 * marks Reminder_Sent = TRUE on the sheet immediately after each send (not
 * batched), and ar_checkWeeklyCompliance's per-area reminded-tracking array
 * is written to PropertiesService in the code path that already runs after
 * a `break` out of the loop — so areas reminded before the stop are recorded
 * and are not re-reminded on the next run; areas not yet reached are simply
 * picked up next run, exactly like the MAX_SENDS pattern already used in
 * CCSM_AgentEscalation.gs.
 *
 * NOTES tab columns:
 *   Note_ID | Area_Code | Area_Name | Author_Email | Note_Text |
 *   Created_At | Reminder_DateTime | Reminder_Sent | Resolved | Resolved_At
 *
 * Config keys read from AGENT_CONFIG:
 *   NIGHTLY_FORM_LINK  — URL for the nightly report form
 *   WEEKLY_FORM_LINK   — URL for the weekly report form
 */


// ── Trigger setup ─────────────────────────────────────────────────────────────

/**
 * DEPRECATED SHIM — delegates to setupAllCcsmTriggers() (CCSM_Setup.gs).
 *
 * This used to install an HOURLY trigger on runReminderAgent(), a handler name
 * CCSM_TRIGGER_SCHEDULE does not know about. Running it after the canonical
 * installer therefore added a second, competing schedule that re-running
 * setupAllCcsmTriggers() could not clear, and NOTES reminders fired 24x a day.
 * The canonical schedule runs this agent Sunday 6 PM through CCSM_Setup.gs's
 * zero-argument runAgentReminder() wrapper.
 *
 * Kept as a shim rather than deleted: it is still in the Apps Script editor's
 * function dropdown and in older setup notes, so converging is the safest
 * thing for it to do when someone picks it by mistake.
 */
function setupReminderTrigger() {
  Logger.log('AgentReminder: setupReminderTrigger() is DEPRECATED — the hourly ' +
    'runReminderAgent trigger it used to install is not on CCSM_TRIGGER_SCHEDULE. ' +
    'Delegating to setupAllCcsmTriggers(); AgentReminder runs Sunday 6 PM as runAgentReminder.');
  setupAllCcsmTriggers();
}


// ── Main agent function ───────────────────────────────────────────────────────

/**
 * Scans NOTES tab and sends reminder emails for notes whose Reminder_DateTime
 * falls between now and 6 hours from now (mission timezone). Then runs the
 * weekly form compliance check.
 *
 * @param {Object} [opts]
 * @param {boolean} [opts.skipTimeGate] — when true, bypasses ONLY
 *   ar_checkWeeklyCompliance()'s Mon/Tue 8 AM–9 PM day/hour gate (see file
 *   header). Intended for automated tests; production trigger calls this
 *   function with no arguments.
 */
function runReminderAgent(opts) {
  try {
    var tz        = getMissionTimezone();
    var now       = new Date();
    var sixHrsMs  = 6 * 60 * 60 * 1000;
    var windowEnd = new Date(now.getTime() + sixHrsMs);

    Logger.log('AgentReminder: starting run at ' +
      Utilities.formatDate(now, tz, 'yyyy-MM-dd HH:mm:ss') +
      ' | window end: ' +
      Utilities.formatDate(windowEnd, tz, 'yyyy-MM-dd HH:mm:ss'));

    // ── Load config ───────────────────────────────────────────────────────────
    var nightlyFormLink = getConfig('NIGHTLY_FORM_LINK') || '';
    var weeklyFormLink  = getConfig('WEEKLY_FORM_LINK')  || '';

    // ── Load NOTES tab ────────────────────────────────────────────────────────
    var sheet  = getTab('NOTES');
    if (!sheet) {
      Logger.log('AgentReminder: NOTES tab not found — aborting.');
      ar_logAudit('ERROR', 0, '', 'NOTES tab not found');
      return;
    }

    var data    = sheet.getDataRange().getValues();
    if (data.length < 2) {
      Logger.log('AgentReminder: NOTES tab is empty — nothing to process.');
    } else {

      var headers           = data[0].map(function(h) { return String(h).trim(); });
      var colNoteId         = headers.indexOf('Note_ID');
      var colAreaName       = headers.indexOf('Area_Name');
      var colAuthorEmail    = headers.indexOf('Author_Email');
      var colNoteText       = headers.indexOf('Note_Text');
      var colReminderDt     = headers.indexOf('Reminder_DateTime');
      var colReminderSent   = headers.indexOf('Reminder_Sent');
      var colResolved       = headers.indexOf('Resolved');

      // Verify required columns exist
      var required = {
        'Note_ID': colNoteId,
        'Author_Email': colAuthorEmail,
        'Note_Text': colNoteText,
        'Reminder_DateTime': colReminderDt,
        'Reminder_Sent': colReminderSent,
        'Resolved': colResolved
      };

      var missingCols = Object.keys(required).filter(function(k) { return required[k] === -1; });
      if (missingCols.length > 0) {
        var msg = 'Missing required columns: ' + missingCols.join(', ');
        Logger.log('AgentReminder: ' + msg);
        ar_logAudit('ERROR', 0, '', msg);
      } else {

        var processed = 0;

        // data row index 0 = headers; data rows 1..n correspond to sheet rows 2..n+1
        for (var i = 1; i < data.length; i++) {
          var row = data[i];

          // ── Filter: skip if Resolved = TRUE ──────────────────────────────────
          var resolved = row[colResolved];
          if (ar_isTruthy(resolved)) continue;

          // ── Filter: skip if Reminder_Sent = TRUE ─────────────────────────────
          var reminderSent = row[colReminderSent];
          if (ar_isTruthy(reminderSent)) continue;

          // ── Filter: skip if Reminder_DateTime is blank or invalid ────────────
          var reminderRaw = row[colReminderDt];
          if (!reminderRaw || String(reminderRaw).trim() === '') continue;

          var reminderDate = ar_parseDate(reminderRaw);
          if (!reminderDate) {
            Logger.log('AgentReminder: row ' + (i + 1) + ' — unparseable Reminder_DateTime: ' + reminderRaw);
            continue;
          }

          // ── Filter: must fall within [now, now + 6 hrs] ───────────────────────
          if (reminderDate < now || reminderDate > windowEnd) continue;

          // ── Quota guard ───────────────────────────────────────────────────────
          // AgentReminder never routes through a relay (see file header), so
          // every send here draws straight from the main account's MailApp
          // quota. Stop cleanly — no thrown exception — once it runs low.
          // Rows already marked Reminder_Sent = TRUE above this point in the
          // loop are untouched, so nothing already sent gets duplicated next run.
          var quota = MailApp.getRemainingDailyQuota();
          if (quota < 20) {
            Logger.log('AgentReminder: daily email quota too low (' + quota + ') — stopping NOTES loop.');
            ar_logAudit('QUOTA_LOW', processed, '', 'Remaining quota: ' + quota);
            break;
          }

          // ── Gather row values ─────────────────────────────────────────────────
          var noteId      = String(row[colNoteId]).trim();
          var areaName    = colAreaName !== -1 ? String(row[colAreaName]).trim() : '';
          var authorEmail = String(row[colAuthorEmail]).trim();
          var noteText    = String(row[colNoteText]).trim();

          if (!authorEmail || !noteText) {
            Logger.log('AgentReminder: row ' + (i + 1) + ' — missing Author_Email or Note_Text, skipping.');
            continue;
          }

          // ── Build email ───────────────────────────────────────────────────────
          var subject  = ar_buildSubject(areaName);
          var bodyHtml = ar_buildEmailBody(noteText, reminderDate, areaName, nightlyFormLink, weeklyFormLink);

          // ── Send email ────────────────────────────────────────────────────────
          sendEmail(authorEmail, subject, bodyHtml, 'AgentReminder');

          Logger.log('AgentReminder: reminder sent to ' + authorEmail +
            ' for note ' + noteId + ' (row ' + (i + 1) + ')');

          // ── Mark Reminder_Sent = TRUE in the sheet ────────────────────────────
          // data row i → sheet row i + 1 (1-based), colReminderSent is 0-based → +1
          sheet.getRange(i + 1, colReminderSent + 1).setValue(true);

          // ── Log to AUDIT_LOG ──────────────────────────────────────────────────
          ar_logAudit('REMINDER_SENT', 1, areaName, noteId);

          processed++;
        }

        Logger.log('AgentReminder: notes run complete — ' + processed + ' reminder(s) sent.');
      }
    }

    // Weekly form compliance reminders — see the file-header "Weekly
    // compliance time gate" note: Mon/Tue 8 AM–9 PM only (unless
    // opts.skipTimeGate), deduped once-per-week per area via PropertiesService.
    var weeklySent = ar_checkWeeklyCompliance(weeklyFormLink, opts);
    if (weeklySent > 0) Logger.log('AgentReminder: weekly compliance sent ' + weeklySent + ' reminder(s).');

  } catch (err) {
    Logger.log('AgentReminder ERROR: ' + err.message + '\n' + err.stack);
    try {
      ar_logAudit('ERROR', 0, '', err.message);
    } catch (logErr) {
      Logger.log('AgentReminder: failed to write error to AUDIT_LOG: ' + logErr.message);
    }
  }
}


// ── Test / dry-run ────────────────────────────────────────────────────────────

/**
 * Dry-run version of runReminderAgent()'s NOTES half.
 * Logs what would be sent without sending any emails or modifying the sheet.
 * Run this manually from the Apps Script editor to verify configuration.
 */
function testReminderAgent() {
  Logger.log('=== AgentReminder DRY RUN ===');

  var tz        = getMissionTimezone();
  var now       = new Date();
  var sixHrsMs  = 6 * 60 * 60 * 1000;
  var windowEnd = new Date(now.getTime() + sixHrsMs);

  Logger.log('Now:         ' + Utilities.formatDate(now,       tz, 'yyyy-MM-dd HH:mm:ss'));
  Logger.log('Window end:  ' + Utilities.formatDate(windowEnd, tz, 'yyyy-MM-dd HH:mm:ss'));

  var nightlyFormLink = getConfig('NIGHTLY_FORM_LINK') || '(not set)';
  var weeklyFormLink  = getConfig('WEEKLY_FORM_LINK')  || '(not set)';
  Logger.log('NIGHTLY_FORM_LINK: ' + nightlyFormLink);
  Logger.log('WEEKLY_FORM_LINK:  ' + weeklyFormLink);

  var sheet = getTab('NOTES');
  if (!sheet) {
    Logger.log('NOTES tab not found — aborting dry run.');
    return;
  }

  var data = sheet.getDataRange().getValues();
  if (data.length < 2) {
    Logger.log('NOTES tab is empty — nothing to process.');
    return;
  }

  var headers         = data[0].map(function(h) { return String(h).trim(); });
  var colNoteId       = headers.indexOf('Note_ID');
  var colAreaName     = headers.indexOf('Area_Name');
  var colAuthorEmail  = headers.indexOf('Author_Email');
  var colNoteText     = headers.indexOf('Note_Text');
  var colReminderDt   = headers.indexOf('Reminder_DateTime');
  var colReminderSent = headers.indexOf('Reminder_Sent');
  var colResolved     = headers.indexOf('Resolved');

  Logger.log('Total data rows (excl. header): ' + (data.length - 1));

  var matchCount = 0;
  var skipReasons = { resolved: 0, sent: 0, noDate: 0, outOfWindow: 0, missingFields: 0 };

  for (var i = 1; i < data.length; i++) {
    var row = data[i];

    if (ar_isTruthy(row[colResolved]))     { skipReasons.resolved++;    continue; }
    if (ar_isTruthy(row[colReminderSent])) { skipReasons.sent++;        continue; }

    var reminderRaw = row[colReminderDt];
    if (!reminderRaw || String(reminderRaw).trim() === '') { skipReasons.noDate++; continue; }

    var reminderDate = ar_parseDate(reminderRaw);
    if (!reminderDate) { skipReasons.noDate++; continue; }

    if (reminderDate < now || reminderDate > windowEnd) { skipReasons.outOfWindow++; continue; }

    var noteId      = colNoteId     !== -1 ? String(row[colNoteId]).trim()      : '(no id)';
    var areaName    = colAreaName   !== -1 ? String(row[colAreaName]).trim()     : '(no area)';
    var authorEmail = colAuthorEmail !== -1 ? String(row[colAuthorEmail]).trim() : '';
    var noteText    = colNoteText   !== -1 ? String(row[colNoteText]).trim()     : '';

    if (!authorEmail || !noteText) { skipReasons.missingFields++; continue; }

    matchCount++;
    Logger.log('  [WOULD SEND] Row ' + (i + 1) +
      ' | Note_ID: '    + noteId +
      ' | Area: '       + areaName +
      ' | To: '         + authorEmail +
      ' | Reminder: '   + Utilities.formatDate(reminderDate, tz, 'yyyy-MM-dd HH:mm:ss') +
      ' | Note: '       + noteText.substring(0, 60) + (noteText.length > 60 ? '...' : ''));
  }

  Logger.log('--- Summary ---');
  Logger.log('Would send:       ' + matchCount);
  Logger.log('Skipped/resolved: ' + skipReasons.resolved);
  Logger.log('Skipped/sent:     ' + skipReasons.sent);
  Logger.log('Skipped/no date:  ' + skipReasons.noDate);
  Logger.log('Skipped/window:   ' + skipReasons.outOfWindow);
  Logger.log('Skipped/fields:   ' + skipReasons.missingFields);
  Logger.log('=== END DRY RUN ===');
}


// ── Private helpers (ar_ prefix) ──────────────────────────────────────────────

/**
 * Returns true if a MISSION_ORG row is a leadership/senior tracking row
 * (never submits the nightly/weekly form → must never receive a reminder).
 * Mirrors a3_isLeadershipRow (CCSM_Agent3.gs).
 */
function ar_isLeadershipRow(areaObj) {
  if ((areaObj['Zone'] || '').toUpperCase() === 'ALL') return true;
  var name = String(areaObj['Area_Name'] || '').trim();
  return /^(Mission President|Assistant to President|Zone Leader|Sister Training Leader -|District Leader -)/i.test(name);
}

/**
 * Returns true if a cell value represents a TRUE-like state.
 * Handles boolean true, string 'true'/'yes'/'1', and number 1.
 *
 * @param {*} val
 * @returns {boolean}
 */
function ar_isTruthy(val) {
  if (typeof val === 'boolean') return val === true;
  if (typeof val === 'number')  return val === 1;
  var s = String(val).trim().toLowerCase();
  return s === 'true' || s === 'yes' || s === '1';
}

/**
 * Parses a value into a Date object. Accepts JS Date objects (passed through
 * from Sheets), date strings, and numeric epoch timestamps.
 * Returns null if the value cannot be parsed into a valid date.
 *
 * @param {*} raw
 * @returns {Date|null}
 */
function ar_parseDate(raw) {
  if (!raw) return null;

  // Sheets often passes Date objects directly
  if (raw instanceof Date) {
    return isNaN(raw.getTime()) ? null : raw;
  }

  // Try numeric timestamp
  if (typeof raw === 'number') {
    var d = new Date(raw);
    return isNaN(d.getTime()) ? null : d;
  }

  // Try string parse
  var str = String(raw).trim();
  if (!str) return null;
  var parsed = new Date(str);
  return isNaN(parsed.getTime()) ? null : parsed;
}

/**
 * Builds the email subject line for a NOTES reminder.
 * @param {string} areaName
 * @returns {string}
 */
function ar_buildSubject(areaName) {
  return 'Recordatorio de Nota — ' + (areaName || '(sin área)');
}

/**
 * Builds an HTML email body for the reminder notification.
 * Detects from note text whether this is a nightly or weekly form reminder
 * and links to the appropriate form.
 *
 * @param {string} noteText
 * @param {Date}   reminderDate
 * @param {string} areaName
 * @param {string} nightlyFormLink — URL for nightly form (from AGENT_CONFIG)
 * @param {string} weeklyFormLink  — URL for weekly form (from AGENT_CONFIG)
 * @returns {string} HTML body
 */
function ar_buildEmailBody(noteText, reminderDate, areaName, nightlyFormLink, weeklyFormLink) {
  var formattedTime = Utilities.formatDate(reminderDate, getMissionTimezone(), 'MMMM d, yyyy \'a las\' h:mm a');

  var lines = [];
  lines.push('<p>Este es un recordatorio automático de <strong>PMG Compass</strong>.</p>');

  if (areaName) {
    lines.push('<p><strong>Área:</strong> ' + ar_escapeHtml(areaName) + '</p>');
  }

  lines.push('<p><strong>Recordatorio programado para:</strong> ' + formattedTime + '</p>');
  lines.push('<hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">');
  lines.push('<p><strong>Nota:</strong></p>');
  lines.push('<blockquote style="margin:0 0 16px 0;padding:12px 16px;' +
    'background:#f9fafb;border-left:4px solid #4f46e5;border-radius:4px;' +
    'font-size:14px;color:#374151;">');
  lines.push(ar_escapeHtml(noteText).replace(/\n/g, '<br>'));
  lines.push('</blockquote>');

  // Detect which form this reminder is for based on note text keywords
  var noteLower   = noteText.toLowerCase();
  var isNightly   = /nocturn|diari/.test(noteLower);
  var isWeekly    = /semanal/.test(noteLower);

  // Show nightly link if note mentions nightly/daily, weekly link if weekly,
  // or both if neither/both matched (catch-all so recipient always has an action link)
  var showNightly = nightlyFormLink && (isNightly || !isWeekly);
  var showWeekly  = weeklyFormLink  && (isWeekly  || !isNightly);

  if (showNightly || showWeekly) {
    lines.push('<p><strong>Enlace' + ((showNightly && showWeekly) ? 's' : '') + ' del formulario:</strong></p><ul>');
    if (showNightly) {
      lines.push('<li><a href="' + nightlyFormLink + '" style="color:#4f46e5;">Formulario de Informe Nocturno</a></li>');
    }
    if (showWeekly) {
      lines.push('<li><a href="' + weeklyFormLink + '" style="color:#4f46e5;">Formulario de Informe Semanal</a></li>');
    }
    lines.push('</ul>');
  }

  lines.push('<p style="color:#6b7280;font-size:12px;margin-top:24px;">— PMG Compass (' + getMissionName() + ')</p>');
  return lines.join('\n');
}

/**
 * Escapes HTML special characters to prevent injection in email bodies.
 *
 * @param {string} str
 * @returns {string}
 */
function ar_escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Weekly form compliance check.
 * Finds active areas that have not submitted WEEKLY_FORM_RAW since last
 * Sunday and sends them a Spanish reminder. Uses PropertiesService so each
 * area is only reminded once per week. Gated to Monday/Tuesday 8 AM–9 PM
 * (mission timezone) — see the file-header "Weekly compliance time gate" note
 * — unless opts.skipTimeGate === true.
 *
 * @param {string} weeklyFormLink
 * @param {Object} [opts]
 * @param {boolean} [opts.skipTimeGate] — bypasses ONLY the day/hour gate.
 * @returns {number} number of reminder emails sent
 */
function ar_checkWeeklyCompliance(weeklyFormLink, opts) {
  var tz = getMissionTimezone();

  // ── Single-owner gate (AGENT_CONFIG: WEEKLY_REMINDER_OWNER) ──────────────
  // This half and CCSM_AgentEscalation.gs's System 2 both email non-submitting
  // companionships about the weekly form, with the SAME Spanish subject —
  // running both double-nags every companionship. Exactly one owns it. The
  // shipped default is AGENT_ESCALATION, so this path is OFF out of the box;
  // see CCSM_Setup.gs's header for the deployment decision. A missing key
  // falls back to the same default, so an older AGENT_CONFIG that predates
  // the row still behaves safely.
  var reminderOwner = String(getConfig('WEEKLY_REMINDER_OWNER') || 'AGENT_ESCALATION').trim().toUpperCase();
  if (reminderOwner !== 'AGENT_REMINDER' && reminderOwner !== 'BOTH') {
    Logger.log('AgentReminder: weekly compliance is owned by ' + reminderOwner +
      ' (AGENT_CONFIG WEEKLY_REMINDER_OWNER) — skipping to avoid duplicate reminders.');
    return 0;
  }

  // ── Determine day name (mission timezone) — also drives the weekKey calc
  //    just below and the day/hour gate right after it. ─────────────────────
  var dayName = Utilities.formatDate(new Date(), tz, 'EEEE');

  // ── Day/hour gate: Monday or Tuesday, 8 AM–9 PM (mission timezone) only.
  //    Restored from the Provo original — see file-header note. The hourly
  //    trigger would otherwise fire this at any hour of any day, including
  //    3 AM. Bypassed ONLY when opts.skipTimeGate === true (tests). ─────────
  var skipTimeGate = !!(opts && opts.skipTimeGate === true);
  if (!skipTimeGate) {
    if (dayName !== 'Monday' && dayName !== 'Tuesday') return 0;
    var gateHour = Number(Utilities.formatDate(new Date(), tz, 'H'));
    if (gateHour < 8 || gateHour >= 21) return 0;
  }

  // ── Determine the most recent Sunday (the missed deadline) ───────────────
  // Includes today if today IS Sunday — matches ae_getLastSunday in
  // CCSM_AgentEscalation.gs.
  var daysBack = {'Sunday':0,'Monday':1,'Tuesday':2,'Wednesday':3,'Thursday':4,'Friday':5,'Saturday':6}[dayName] || 0;
  var weekKey  = Utilities.formatDate(new Date(new Date().getTime() - daysBack * 86400000), tz, 'yyyy-MM-dd');

  // ── Never remind for a week that ended before the system launched ────────
  var systemStart = ar_systemStartStr();
  if (systemStart && weekKey < systemStart) {
    Logger.log('AgentReminder: weekly week=' + weekKey + ' is before SYSTEM_START_DATE ' +
      systemStart + ' — skipping.');
    return 0;
  }

  Logger.log('AgentReminder: weekly compliance check | week=' + weekKey + ' | day=' + dayName);

  // ── Load WEEKLY_FORM_RAW ──────────────────────────────────────────────────
  // The weekly form is multi-section (one "¿En qué área sirve?" column per
  // zone) so scan EVERY area column case-insensitively — a single indexOf()
  // lookup would only ever see the first zone's section.
  var submittedAreas = {};
  var rawSheet = getTab('WEEKLY_FORM_RAW');
  if (rawSheet) {
    var rawData = rawSheet.getDataRange().getValues();
    if (rawData.length > 1) {
      var rawHeaders   = rawData[0].map(function(h) { return String(h).trim().toLowerCase(); });
      var rawAreaCols  = [];
      rawHeaders.forEach(function(h, idx) {
        if (h === '¿en qué área sirve?') rawAreaCols.push(idx);
      });
      if (rawAreaCols.length > 0) {
        for (var i = 1; i < rawData.length; i++) {
          var ts = rawData[i][0]; // Timestamp is always col 0 (Marca temporal)
          if (!(ts instanceof Date) || isNaN(ts.getTime())) continue;
          if (Utilities.formatDate(ts, tz, 'yyyy-MM-dd') < weekKey) continue;
          for (var c = 0; c < rawAreaCols.length; c++) {
            var area = String(rawData[i][rawAreaCols[c]] || '').trim();
            if (area) { submittedAreas[area.toLowerCase()] = true; break; }
          }
        }
      } else {
        Logger.log('AgentReminder: WEEKLY_FORM_RAW has no "¿En qué área sirve?" column — treating all areas as non-submitting would be wrong, so skipping weekly check.');
        return 0;
      }
    }
  }

  Logger.log('AgentReminder: submitted this week: ' + Object.keys(submittedAreas).join(', '));

  // ── Load MISSION_ORG ──────────────────────────────────────────────────────
  var orgSheet = getTab('MISSION_ORG');
  if (!orgSheet) return 0;
  var orgData = orgSheet.getDataRange().getValues();
  if (orgData.length < 2) return 0;

  var oh       = orgData[0].map(function(h) { return String(h).trim(); });
  var colArea  = oh.indexOf('Area_Name');
  var colZone  = oh.indexOf('Zone');
  var colE1    = oh.indexOf('Companion1_Email');
  var colE2    = oh.indexOf('Companion2_Email');
  var colAct   = oh.indexOf('Active');
  if (colArea === -1) return 0;

  // ── Already-reminded tracking (once per week per area) ───────────────────
  var props       = PropertiesService.getScriptProperties();
  var propKey     = 'AR_WEEKLY_REMINDED_' + weekKey;
  var remindedStr = props.getProperty(propKey) || '';
  var reminded    = remindedStr ? remindedStr.split(',') : [];
  var newReminded = reminded.slice();
  var sent        = 0;

  try {
    for (var i = 1; i < orgData.length; i++) {
      var row = orgData[i];
  
      // Skip inactive areas
      if (colAct !== -1 && String(row[colAct]).trim().toUpperCase() !== 'TRUE') continue;
  
      var areaName = String(row[colArea] || '').trim();
      if (!areaName) continue;
  
      // Skip leadership/senior tracking rows (never submit → never remind them)
      if (ar_isLeadershipRow({
        'Zone':      colZone !== -1 ? String(row[colZone] || '') : '',
        'Area_Name': areaName
      })) continue;
  
      // Skip if already submitted or already reminded this week
      if (submittedAreas[areaName.toLowerCase()]) continue;
      if (reminded.indexOf(areaName.toLowerCase()) !== -1) continue;
  
      // Collect companion emails — skip blanks and placeholders.
      var emails = [];
      [colE1, colE2].forEach(function(col) {
        if (col === -1) return;
        var e = String(row[col] || '').trim();
        if (!e || e.indexOf('@') < 0) return;
        var lower = e.toLowerCase();
        if (lower.indexOf('notreadyyet') >= 0 || lower.indexOf('tbd@') >= 0) return;
        emails.push(e);
      });
      if (emails.length === 0) continue;
  
      // ── Quota guard ─────────────────────────────────────────────────────────
      // Same reasoning as the NOTES loop above (see file header): no relay for
      // AgentReminder, so stop cleanly before the main account's MailApp quota
      // runs out. `newReminded` (and therefore PropertiesService) is written in
      // the `finally` on this loop regardless of whether we `break` out early,
      // finish normally, or a send throws — so every area already reminded
      // before the stop is recorded, and the next run picks up exactly where
      // this one left off rather than re-sending to everyone.
      var quota = MailApp.getRemainingDailyQuota();
      if (quota < 20) {
        Logger.log('AgentReminder: daily email quota too low (' + quota + ') — stopping weekly compliance early.');
        ar_logAudit('QUOTA_LOW', sent, '', 'Remaining quota: ' + quota);
        break;
      }
  
      var subject = 'Recordatorio: Informe Semanal — ' + getMissionName();
      var body    = ar_buildWeeklyComplianceBody(areaName, weekKey, weeklyFormLink);
      emails.forEach(function(email) {
        sendEmail(email, subject, body, 'AgentReminder');
      });
  
      Logger.log('AgentReminder: weekly reminder → ' + areaName + ' (' + emails.join(', ') + ')');
      ar_logAudit('WEEKLY_REMINDER_SENT', emails.length, areaName, weekKey);
  
      newReminded.push(areaName.toLowerCase());
      sent++;
    }
  } finally {
    // Load-bearing: a thrown send must not discard the areas already reminded,
    // or the next run re-sends the weekly reminder to every one of them.
    if (newReminded.length > reminded.length) {
      props.setProperty(propKey, newReminded.join(','));
    }
  }

  Logger.log('AgentReminder: weekly compliance done — ' + sent + ' sent for week ' + weekKey);
  return sent;
}


/**
 * HTML email body for the weekly form compliance reminder (Spanish).
 */
function ar_buildWeeklyComplianceBody(areaName, weekKey, weeklyFormLink) {
  var lines = [];
  lines.push('<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:640px;margin:0 auto;">');
  lines.push('<h2 style="color:#1a4d7c;">Recordatorio de Informe Semanal</h2>');
  lines.push('<p>¡Hola! Este es su recordatorio para enviar el informe semanal de esta semana.</p>');
  lines.push('<p>Estimados misioneros de <strong>' + ar_escapeHtml(areaName) + '</strong>:</p>');
  lines.push('<p>Notamos que su <strong>informe semanal</strong> para la semana del <strong>');
  lines.push(ar_escapeHtml(weekKey) + '</strong> aún no ha sido enviado.</p>');
  if (weeklyFormLink) {
    lines.push('<p style="margin-top:20px;"><a href="' + ar_escapeHtml(weeklyFormLink) + '" ');
    lines.push('style="background:#1a4d7c;color:#fff;padding:10px 20px;text-decoration:none;');
    lines.push('border-radius:4px;font-weight:bold;">Enviar Informe Ahora</a></p>');
  }
  lines.push('<p style="margin-top:20px;">¡Gracias por su fidelidad y por el gran trabajo que están haciendo!</p>');
  lines.push('<p style="color:#6b7280;font-size:12px;margin-top:24px;">— PMG Compass (' + getMissionName() + ')</p>');
  lines.push('</body></html>');
  return lines.join('\n');
}


/**
 * Returns SYSTEM_START_DATE from AGENT_CONFIG as a clean 'yyyy-MM-dd' string,
 * or '' if unset. AGENT_CONFIG date cells come back as Date OBJECTS, so a raw
 * String() would break the lexical weekKey comparison — normalize first.
 */
function ar_systemStartStr() {
  var raw = getConfig('SYSTEM_START_DATE');
  if (raw === null || raw === undefined || raw === '') return '';
  var tz = getMissionTimezone();
  if (raw instanceof Date) {
    return isNaN(raw.getTime()) ? '' : Utilities.formatDate(raw, tz, 'yyyy-MM-dd');
  }
  var m = String(raw).trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return m[1] + '-' + m[2] + '-' + m[3];
  var d = new Date(String(raw).trim());
  return isNaN(d.getTime()) ? '' : Utilities.formatDate(d, tz, 'yyyy-MM-dd');
}

/**
 * BLAST-RADIUS PREVIEW for the weekly compliance reminder. Sends NOTHING and
 * changes nothing — reports how many areas WOULD be reminded for the most
 * recent week, honoring the SYSTEM_START_DATE guard and the once-per-week
 * dedup.
 */
function previewWeeklyCompliance() {
  var tz      = getMissionTimezone();
  var now     = new Date();
  var dayName = Utilities.formatDate(now, tz, 'EEEE');
  var back    = {'Sunday':0,'Monday':1,'Tuesday':2,'Wednesday':3,'Thursday':4,'Friday':5,'Saturday':6}[dayName] || 0;
  var weekKey = Utilities.formatDate(new Date(now.getTime() - back * 86400000), tz, 'yyyy-MM-dd');

  Logger.log('=== previewWeeklyCompliance (NO emails sent) ===');
  Logger.log('Today: ' + dayName + ' | most recent Sunday (week deadline): ' + weekKey);

  var systemStart = ar_systemStartStr();
  Logger.log('SYSTEM_START_DATE: ' + (systemStart || '(unset)'));
  if (systemStart && weekKey < systemStart) {
    Logger.log('week ' + weekKey + ' is before launch → real run would send 0.');
    Logger.log('=== END preview ==='); return;
  }

  // Areas that submitted the weekly form on/after weekKey — multi-section
  // form, so scan every "¿En qué área sirve?" column (case-insensitive).
  var submitted = {};
  var rawSheet = getTab('WEEKLY_FORM_RAW');
  if (rawSheet) {
    var rawData = rawSheet.getDataRange().getValues();
    if (rawData.length > 1) {
      var rh   = rawData[0].map(function(h){ return String(h).trim().toLowerCase(); });
      var racs = [];
      rh.forEach(function(h, idx) { if (h === '¿en qué área sirve?') racs.push(idx); });
      for (var i = 1; i < rawData.length; i++) {
        var ts = rawData[i][0];
        if (!(ts instanceof Date) || isNaN(ts.getTime())) continue;
        if (Utilities.formatDate(ts, tz, 'yyyy-MM-dd') < weekKey) continue;
        for (var c = 0; c < racs.length; c++) {
          var a = String(rawData[i][racs[c]] || '').trim();
          if (a) { submitted[a.toLowerCase()] = true; break; }
        }
      }
    }
  }

  var props    = PropertiesService.getScriptProperties();
  var reminded = (props.getProperty('AR_WEEKLY_REMINDED_' + weekKey) || '').split(',').filter(Boolean);

  var orgSheet = getTab('MISSION_ORG');
  var orgData  = orgSheet ? orgSheet.getDataRange().getValues() : [];
  var willSend = [], submittedOk = [], alreadyReminded = [], noEmail = [], nonSub = [];

  if (orgData.length > 1) {
    var oh = orgData[0].map(function(h){ return String(h).trim(); });
    var cA = oh.indexOf('Area_Name'), cZ = oh.indexOf('Zone'), cAct = oh.indexOf('Active');
    var cE1 = oh.indexOf('Companion1_Email'), cE2 = oh.indexOf('Companion2_Email');

    for (var r = 1; r < orgData.length; r++) {
      var row = orgData[r];
      if (cAct !== -1 && String(row[cAct]).trim().toUpperCase() !== 'TRUE') continue;
      var area = String(row[cA] || '').trim();
      if (!area) continue;
      if (ar_isLeadershipRow({
        'Zone':      cZ !== -1 ? String(row[cZ] || '') : '',
        'Area_Name': area
      })) { nonSub.push(area); continue; }
      if (submitted[area.toLowerCase()])               { submittedOk.push(area);     continue; }
      if (reminded.indexOf(area.toLowerCase()) !== -1) { alreadyReminded.push(area); continue; }
      var emails = [cE1, cE2].map(function(c){ return c !== -1 ? String(row[c] || '').trim() : ''; })
        .filter(function(e){
          if (!e || e.indexOf('@') < 0) return false;
          var lower = e.toLowerCase();
          return lower.indexOf('notreadyyet') < 0 && lower.indexOf('tbd@') < 0;
        });
      if (!emails.length) { noEmail.push(area); continue; }
      willSend.push(area);
    }
  }

  Logger.log('WOULD SEND weekly reminder to: ' + willSend.length + ' area(s)');
  Logger.log('Already submitted this week:   ' + submittedOk.length);
  Logger.log('Already reminded this week:    ' + alreadyReminded.length);
  Logger.log('Skipped — no valid email:      ' + noEmail.length);
  Logger.log('Skipped — leadership/AP/MP:    ' + nonSub.length);
  if (willSend.length) Logger.log('Would send to: ' + willSend.join(', '));
  Logger.log('=== END preview ===');
}

/**
 * Appends a row to the AUDIT_LOG tab.
 *
 * @param {string} action        — e.g. 'REMINDER_SENT', 'ERROR'
 * @param {number} rowsAffected
 * @param {string} area
 * @param {string} notes
 */
function ar_logAudit(action, rowsAffected, area, notes) {
  try {
    var sheet = getTab('AUDIT_LOG');
    if (!sheet) return;

    // Bootstrap header row if the sheet is empty
    var lastCol = sheet.getLastColumn();
    if (lastCol === 0 || sheet.getLastRow() === 0) {
      sheet.appendRow(['Timestamp', 'Agent', 'Action', 'Rows_Affected', 'Area', 'Notes']);
    }

    sheet.appendRow([
      Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd HH:mm:ss'),
      'AgentReminder',
      action,
      rowsAffected,
      area,
      notes
    ]);
  } catch (e) {
    Logger.log('ar_logAudit failed: ' + e.message);
  }
}
