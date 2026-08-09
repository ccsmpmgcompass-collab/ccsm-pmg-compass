/**
 * ============================================================
 * CCSM_AgentEscalation.gs — Escalation Agent
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of AgentEscalation.gs (docs/AgentEscalation.gs in PMG-Compass).
 * Internal ae_* function names are kept identical to the Provo original so
 * future diffs stay readable.
 *
 * System 1 — Nightly Form Escalation (daily trigger ~10 AM, mission timezone):
 *   Day+2 10 AM  → Reminder 1 to companions
 *   Day+3 10 AM  → Reminder 2 to companions   (only if Reminder 1 was sent)
 *   Day+4 10 AM  → Escalation to leader        (only if Reminder 2 was sent)
 *
 * System 2 — Weekly Form Escalation (daily trigger ~8:45 PM, mission
 * timezone, Mon–Wed only):
 *   Monday    8:45 PM → Reminder 1 to companions
 *   Tuesday   8:45 PM → Reminder 2 to companions   (only if Reminder 1 was sent)
 *   Wednesday 8:45 PM → Escalation to leader        (only if Reminder 2 was sent)
 *
 * Escalation chain:
 *   Regular area / STL  → DL of their district
 *   District Leader     → ZL of their zone
 *   Zone Leader          → DL of their district
 *   AP / Zone=ALL       → skipped (district not determinable)
 *
 * IMPORTANT: if CCSM_AgentReminder.gs's weekly compliance check
 * (ar_checkWeeklyCompliance) is also enabled, both agents will independently
 * remind non-submitting areas of the weekly form — pick one mechanism in
 * production, same caution the Provo original calls out for its own
 * AgentReminder.gs. Task 14 turned that caution into an enforced
 * single-owner gate: AGENT_CONFIG's WEEKLY_REMINDER_OWNER selects the owner,
 * and runWeeklyEscalation() returns immediately unless it is the owner. The
 * SHIPPED DEFAULT is AGENT_ESCALATION, i.e. System 2 owns weekly reminders
 * out of the box. System 1 (nightly) is unaffected by the setting. See
 * CCSM_Setup.gs's header for the full deployment decision.
 *
 * Deviation — the Provo timezone literal is replaced with
 * getMissionTimezone() everywhere (grepped clean, see task report), and
 * resolveTabName() is not called: CCSM has not
 * forked TEST_MODE tab routing yet (a later task), and no other CCSM agent
 * (CCSM_Agent3.gs, CCSM_Agent5A.gs) calls it either — both read
 * NIGHTLY_FORM_RAW / WEEKLY_FORM_RAW via a plain getTab() call, so this file
 * matches that established convention instead of referencing an undefined
 * function.
 *
 * Gmail quota guard (restored from Provo, code review finding): CCSM's
 * sendEmail() (CCSM_Helpers.gs) routes 'AgentEscalation' traffic through
 * RELAY_2_URL (UrlFetchApp) when it and RELAY_SECRET are both configured,
 * which does NOT consume the main account's MailApp quota — but CCSM's
 * shipped default has RELAY_2_URL empty, so out of the box every send here
 * falls through to MailApp.sendEmail() against the main account's daily
 * Gmail quota. ae_relayConfigured() mirrors that same routing check, so both
 * runNightlyEscalation() and runWeeklyEscalation() only enforce the MailApp
 * quota guard when the relay is NOT configured. Both stop cleanly (no thrown
 * exception, using the same capHit flag already used for MAX_SENDS) once the
 * quota drops below 20. props.setProperties(updates) runs in a `finally` on
 * each run's forEach loop — so it persists whether the loop finished, capHit
 * stopped it early, OR a send threw (the relay fallback can raise a MailApp
 * quota exception). Every area/date already updated before the stop is
 * persisted and is not re-sent on the next run; areas not yet reached stay at
 * their prior stage and are simply picked up next run.
 *
 * The `finally` is load-bearing, not defensive style: without it a single
 * thrown send discards every stage advance made in that run, and the next
 * morning's run re-sends every reminder to everyone already emailed.
 *
 * Deviation — ae_loadWeeklySubmissions() now scans EVERY "¿En qué área
 * sirve?" column occurrence (case-insensitive), not just the first. The
 * CCSM weekly form is multi-section — one area column repeats per zone (see
 * CCSM_Agent3.gs a3_parseSectionStructure / fixtures.js) — so a single
 * indexOf() lookup would only ever see the first zone's submissions. This
 * mirrors the fix CCSM_AgentReminder.gs's ar_checkWeeklyCompliance already
 * applies to the same column.
 *
 * State tracking: PropertiesService (ScriptProperties)
 *   Key:   ESC_N_<areaName>_<yyyy-MM-dd>   (nightly, one key per area per date)
 *          ESC_W_<areaName>_<yyyy-MM-dd>   (weekly, one key per area per week-end Sunday)
 *   Value: "0"    = no action yet
 *          "1"    = Reminder 1 sent
 *          "2"    = Reminder 2 sent
 *          "3"    = Escalation sent
 *          "DONE" = form was submitted — stop all notifications
 *
 * Required AGENT_CONFIG keys:
 *   NIGHTLY_FORM_LINK    — full URL of the nightly Google Form
 *   WEEKLY_FORM_LINK     — full URL of the weekly Google Form
 *   MISSED_DAYS_LOOKBACK — days to scan back (default: 14)
 */


// ─────────────────────────────────────────────────────────────────────────────
// TRIGGER SETUP
// ─────────────────────────────────────────────────────────────────────────────

/**
 * DEPRECATED SHIM — delegates to setupAllCcsmTriggers() (CCSM_Setup.gs).
 *
 * This used to install two daily triggers of its own — runNightlyEscalation at
 * 10:00 and runWeeklyEscalation at 20:45 — neither of which is a handler name
 * CCSM_TRIGGER_SCHEDULE knows about. Running it after the canonical installer
 * therefore left escalation firing at 07:00 AND 10:00 AND 20:45, and
 * re-running setupAllCcsmTriggers() could not clear the extras. The canonical
 * schedule runs BOTH systems once a day at 07:00 through CCSM_Setup.gs's
 * zero-argument runAgentEscalation() wrapper.
 *
 * Kept as a shim rather than deleted: it is still in the Apps Script editor's
 * function dropdown and in older setup notes, so converging is the safest
 * thing for it to do when someone picks it by mistake.
 */
function setupEscalationTriggers() {
  Logger.log('AgentEscalation: setupEscalationTriggers() is DEPRECATED — the 10:00 / 20:45 ' +
    'triggers it used to install are not on CCSM_TRIGGER_SCHEDULE and would double up on the ' +
    '07:00 runAgentEscalation trigger. Delegating to setupAllCcsmTriggers().');
  setupAllCcsmTriggers();
}


// ─────────────────────────────────────────────────────────────────────────────
// SYSTEM 1 — NIGHTLY FORM ESCALATION
// ─────────────────────────────────────────────────────────────────────────────

function runNightlyEscalation() {
  // ── TEST GUARDS — PRODUCTION DEFAULTS ARE BOTH OFF ───────────────────────────
  // Leave these as '' and 0 for normal operation (the daily trigger reminds every
  // area). Set them ONLY for a manual test run, then change them back.
  //   TEST_AREA_ONLY : '' = all areas.  Set to an exact Area_Name to email ONLY it.
  //   MAX_SENDS      :  0 = no cap.     Set >0 to stop after N emails this run.
  // Areas not reached stay at stage 0 and are picked up on the next run — no one
  // is ever dropped; the chain just shifts to the next day.
  var TEST_AREA_ONLY = '';
  var MAX_SENDS      = 0;
  // ─────────────────────────────────────────────────────────────────────────────

  var tz  = getMissionTimezone();
  var now = new Date();
  Logger.log('AgentEscalation System 1: starting ' +
    Utilities.formatDate(now, tz, 'yyyy-MM-dd HH:mm:ss') +
    (TEST_AREA_ONLY ? ' [TEST_AREA_ONLY=' + TEST_AREA_ONLY + ']' : '') +
    (MAX_SENDS ? ' [MAX_SENDS=' + MAX_SENDS + ']' : ''));

  ae_purgeOldKeys();

  var missionOrg = ae_loadMissionOrg();
  if (!missionOrg.length) { Logger.log('AgentEscalation: MISSION_ORG empty'); return; }

  var formLink    = getConfig('NIGHTLY_FORM_LINK') || '';
  var lookback    = Math.max(4, parseInt(getConfig('MISSED_DAYS_LOOKBACK') || '14', 10));
  var systemStart = ae_cfgDateStr('SYSTEM_START_DATE');
  var submitted   = ae_loadNightlySubmissions(lookback);
  var today       = Utilities.formatDate(now, tz, 'yyyy-MM-dd');
  var todayMs     = new Date(today + 'T00:00:00').getTime();

  // Escalation emails route through RELAY_2_URL (UrlFetchApp), which does NOT
  // consume the main account's MailApp quota. Only enforce the MailApp quota
  // guard when the relay is NOT configured (so we'd fall back to the main send).
  var usingRelay = ae_relayConfigured();

  // Read all PropertiesService keys at once for efficiency
  var props    = PropertiesService.getScriptProperties();
  var allProps = props.getProperties();
  var updates  = {};
  var sent     = 0;
  var capHit   = false;

  try {
    missionOrg.forEach(function(areaObj) {
      if (capHit) return;                                   // MAX_SENDS reached — stop
      if (ae_isNonSubmitting(areaObj)) return;
  
      var areaName   = String(areaObj['Area_Name'] || '').trim();
      if (TEST_AREA_ONLY && areaName !== TEST_AREA_ONLY) return;   // test: one area only
      var companions = ae_getCompanionEmails(areaObj);
      if (!areaName || !companions) return;
  
      var areaSubmitted = submitted[areaName] || {};
  
      for (var d = 2; d <= lookback; d++) {
        var missedMs   = todayMs - d * 86400000;
        var missedDate = Utilities.formatDate(new Date(missedMs), tz, 'yyyy-MM-dd');
        if (systemStart && missedDate < systemStart) continue;
        var propKey    = 'ESC_N_' + areaName + '_' + missedDate;
        var stage      = updates[propKey] || allProps[propKey] || '0';
  
        // Form was (late-)submitted — cancel any pending notifications
        if (areaSubmitted[missedDate]) {
          if (stage !== '0' && stage !== 'DONE') updates[propKey] = 'DONE';
          continue;
        }
  
        if (stage === 'DONE' || stage === '3') continue;
  
        if (MAX_SENDS > 0 && sent >= MAX_SENDS) {
          Logger.log('AgentEscalation: MAX_SENDS (' + MAX_SENDS + ') reached — stopping.');
          capHit = true;
          break;
        }
  
        if (!usingRelay && MailApp.getRemainingDailyQuota() < 20) {
          Logger.log('AgentEscalation: main-account quota too low and no relay — stopping.');
          capHit = true;
          break;
        }
  
        if (d >= 4 && stage === '2') {
          // Escalation to district/zone leader
          var escEmail = ae_getEscalationEmail(areaObj, missionOrg);
          if (!escEmail) { continue; }
          var subject = 'Escalamiento: Informes Faltantes — ' + areaName;
          var body    = ae_buildNightlyEscalationBody(areaName, missedDate, formLink);
          sendEmail(escEmail, subject, body, 'AgentEscalation');
          updates[propKey] = '3';
          ae_logAudit('NIGHTLY_ESCALATED', areaName, missedDate, escEmail);
          sent++;
  
        } else if (d >= 3 && stage === '1') {
          // Reminder 2
          var subject = 'Segundo Recordatorio: Informe Nocturno No Enviado — ' + areaName;
          var body    = ae_buildNightlyReminderBody(areaName, missedDate, 2, formLink);
          sendEmail(companions, subject, body, 'AgentEscalation');
          updates[propKey] = '2';
          ae_logAudit('NIGHTLY_REMINDER_2', areaName, missedDate, companions);
          sent++;
  
        } else if (d >= 2 && stage === '0') {
          // Reminder 1
          var subject = 'Recordatorio: Informe Nocturno No Enviado — ' + areaName;
          var body    = ae_buildNightlyReminderBody(areaName, missedDate, 1, formLink);
          sendEmail(companions, subject, body, 'AgentEscalation');
          updates[propKey] = '1';
          ae_logAudit('NIGHTLY_REMINDER_1', areaName, missedDate, companions);
          sent++;
        }
      }
    });
  } finally {
    // Load-bearing: persist stage advances even if a send threw. See file header.
    if (Object.keys(updates).length) props.setProperties(updates);
  }

  Logger.log('AgentEscalation System 1: done — ' + sent + ' action(s).');
}


// ─────────────────────────────────────────────────────────────────────────────
// SYSTEM 2 — WEEKLY FORM ESCALATION
// ─────────────────────────────────────────────────────────────────────────────

/**
 * @param {Object} [opts]
 * @param {number} [opts.forceStage] — when 1, 2 or 3, bypasses ONLY the Mon–Wed
 *   day-to-stage gate below and runs that stage directly. Intended for
 *   automated tests, which must not depend on which real weekday the suite
 *   happens to run on. Mirrors the existing runReminderAgent({skipTimeGate})
 *   pattern: the production trigger (CCSM_Setup.gs runAgentEscalation) calls
 *   this with NO arguments, so the day gate is always active in production.
 */
function runWeeklyEscalation(opts) {
  // ── TEST GUARDS — PRODUCTION DEFAULTS ARE BOTH OFF (see runNightlyEscalation) ──
  var TEST_AREA_ONLY = '';
  var MAX_SENDS      = 0;
  // ─────────────────────────────────────────────────────────────────────────────

  // ── Single-owner gate (AGENT_CONFIG: WEEKLY_REMINDER_OWNER) ──────────────
  // This system and CCSM_AgentReminder.gs's ar_checkWeeklyCompliance() both
  // email non-submitting companionships about the weekly form, with the SAME
  // Spanish subject — running both double-nags every companionship. Exactly
  // one owns it; the shipped default is AGENT_ESCALATION (this path). See
  // CCSM_Setup.gs's header for the deployment decision. A missing key falls
  // back to the same default.
  var reminderOwner = String(getConfig('WEEKLY_REMINDER_OWNER') || 'AGENT_ESCALATION').trim().toUpperCase();
  if (reminderOwner !== 'AGENT_ESCALATION' && reminderOwner !== 'BOTH') {
    Logger.log('AgentEscalation System 2: weekly reminders are owned by ' + reminderOwner +
      ' (AGENT_CONFIG WEEKLY_REMINDER_OWNER) — skipping to avoid duplicate reminders.');
    return;
  }

  var tz      = getMissionTimezone();
  var now     = new Date();
  var dayName = Utilities.formatDate(now, tz, 'EEEE');
  var forced  = opts && [1, 2, 3].indexOf(opts.forceStage) !== -1 ? opts.forceStage : null;
  var stageForDay = forced || {'Monday': 1, 'Tuesday': 2, 'Wednesday': 3}[dayName];
  if (!stageForDay) return; // Only Mon–Wed

  Logger.log('AgentEscalation System 2: starting ' +
    Utilities.formatDate(now, tz, 'yyyy-MM-dd HH:mm') +
    ' (' + dayName + ' → stage ' + stageForDay + ')');

  var missionOrg = ae_loadMissionOrg();
  if (!missionOrg.length) return;

  var formLink    = getConfig('WEEKLY_FORM_LINK') || '';
  var weekKey     = ae_getLastSunday(tz);
  var systemStart = ae_cfgDateStr('SYSTEM_START_DATE');
  if (systemStart && weekKey < systemStart) {
    Logger.log('AgentEscalation System 2: weekKey ' + weekKey + ' is before SYSTEM_START_DATE ' + systemStart + ' — skipping.');
    return;
  }
  var submitted = ae_loadWeeklySubmissions(weekKey);

  var props    = PropertiesService.getScriptProperties();
  var allProps = props.getProperties();
  var updates  = {};
  var sent     = 0;
  var capHit   = false;

  try {
    missionOrg.forEach(function(areaObj) {
      if (capHit) return;                                          // MAX_SENDS reached
      if (ae_isNonSubmitting(areaObj)) return;
  
      var areaName   = String(areaObj['Area_Name'] || '').trim();
      if (TEST_AREA_ONLY && areaName !== TEST_AREA_ONLY) return;   // test: one area only
      var companions = ae_getCompanionEmails(areaObj);
      if (!areaName || !companions) return;
  
      if (MAX_SENDS > 0 && sent >= MAX_SENDS) { capHit = true; return; }
  
      var propKey      = 'ESC_W_' + areaName + '_' + weekKey;
      var currentStage = parseInt(updates[propKey] || allProps[propKey] || '0', 10);
  
      // Form submitted — mark DONE and stop
      if (submitted[areaName.toLowerCase()]) {
        if (!isNaN(currentStage) && currentStage > 0) updates[propKey] = 'DONE';
        return;
      }
  
      var stageStr = updates[propKey] || allProps[propKey] || '0';
      if (stageStr === 'DONE') return;
      if (currentStage >= stageForDay) return;           // already at or past today's stage
      if (currentStage !== stageForDay - 1) return;      // requires previous stage first
  
      if (!ae_relayConfigured() && MailApp.getRemainingDailyQuota() < 20) {
        Logger.log('AgentEscalation: main-account quota too low and no relay — stopping.');
        capHit = true;
        return;
      }
  
      if (stageForDay === 1) {
        var subject = 'Recordatorio: Informe Semanal — ' + getMissionName();
        var body    = ae_buildWeeklyReminderBody(areaName, weekKey, 1, formLink);
        sendEmail(companions, subject, body, 'AgentEscalation');
        updates[propKey] = '1';
        ae_logAudit('WEEKLY_REMINDER_1', areaName, weekKey, companions);
        sent++;
  
      } else if (stageForDay === 2) {
        var subject = 'Segundo Recordatorio: Informe Semanal No Enviado — ' + areaName;
        var body    = ae_buildWeeklyReminderBody(areaName, weekKey, 2, formLink);
        sendEmail(companions, subject, body, 'AgentEscalation');
        updates[propKey] = '2';
        ae_logAudit('WEEKLY_REMINDER_2', areaName, weekKey, companions);
        sent++;
  
      } else if (stageForDay === 3) {
        var escEmail = ae_getEscalationEmail(areaObj, missionOrg);
        if (!escEmail) return;
        var subject = 'Escalamiento: Informes Faltantes — ' + areaName;
        var body    = ae_buildWeeklyEscalationBody(areaName, weekKey, formLink);
        sendEmail(escEmail, subject, body, 'AgentEscalation');
        updates[propKey] = '3';
        ae_logAudit('WEEKLY_ESCALATED', areaName, weekKey, escEmail);
        sent++;
      }
    });
  } finally {
    // Load-bearing: persist stage advances even if a send threw. See file header.
    if (Object.keys(updates).length) props.setProperties(updates);
  }

  Logger.log('AgentEscalation System 2: done — ' + sent + ' action(s).');
}


// ─────────────────────────────────────────────────────────────────────────────
// ESCALATION ROUTING
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Returns the escalation recipient email string (comma-joined companions).
 *
 * Chain:
 *   Regular area / STL  → DL of their district
 *   District Leader     → ZL of their zone
 *   Zone Leader          → DL of their district
 *   Zone=ALL (APs)       → null (skipped — district not determinable)
 *
 * Self-escalation guard: if the found leader's email overlaps with the missing
 * area's own companions (e.g. the DL's own area forgets), steps up to ZL instead.
 */
function ae_getEscalationEmail(areaObj, missionOrg) {
  var isDL  = String(areaObj['Is_DL'] || '').toUpperCase() === 'TRUE';
  var zone  = String(areaObj['Zone']     || '').trim();
  var dist  = String(areaObj['District'] || '').trim();

  var leader;

  if (isDL) {
    // District leader → ZL of their zone
    leader = ae_findLeaderRow(missionOrg, 'Is_ZL', 'Zone', zone);
    if (!leader) {
      Logger.log('AgentEscalation: no ZL for zone "' + zone + '" — escalation skipped');
      return null;
    }
  } else if (!dist || dist.toUpperCase() === 'ALL') {
    // ZL or STL with District=ALL — no specific district assigned.
    // Escalate to the first DL found in their zone.
    leader = ae_findLeaderRow(missionOrg, 'Is_DL', 'Zone', zone);
    if (!leader) {
      Logger.log('AgentEscalation: no DL in zone "' + zone + '" for ZL/STL — escalation skipped');
      return null;
    }
  } else {
    // Regular area → DL of their district
    leader = ae_findLeaderRow(missionOrg, 'Is_DL', 'District', dist);
    if (!leader) {
      Logger.log('AgentEscalation: no DL for district "' + dist + '" — escalation skipped');
      return null;
    }
  }

  var escEmail   = ae_getCompanionEmails(leader);
  var companions = ae_getCompanionEmails(areaObj);

  // Self-escalation guard: the found leader IS a companion in the missing area
  // (e.g. the DL's own area missed a form). Step up to ZL instead.
  if (escEmail && companions && ae_emailsOverlap(escEmail, companions)) {
    Logger.log('AgentEscalation: self-escalation detected for "' + areaObj['Area_Name'] +
      '" — stepping up to ZL of zone "' + zone + '"');
    var zlRow = ae_findLeaderRow(missionOrg, 'Is_ZL', 'Zone', zone);
    if (!zlRow) {
      Logger.log('AgentEscalation: no ZL for zone "' + zone + '" — escalation skipped');
      return null;
    }
    var zlEmail = ae_getCompanionEmails(zlRow);
    if (zlEmail && ae_emailsOverlap(zlEmail, companions)) {
      Logger.log('AgentEscalation: ZL is also the area — no valid escalation recipient');
      return null;
    }
    return zlEmail;
  }

  return escEmail;
}

/** Finds the first MISSION_ORG row where row[flag]='TRUE' and row[field]=value. */
function ae_findLeaderRow(missionOrg, flag, field, value) {
  for (var i = 0; i < missionOrg.length; i++) {
    var row = missionOrg[i];
    if (String(row[flag]  || '').toUpperCase() === 'TRUE' &&
        String(row[field] || '').trim()         === value) {
      return row;
    }
  }
  return null;
}

/**
 * Returns true if any individual email in setA also appears in setB.
 * Both inputs are comma-separated email strings.
 */
function ae_emailsOverlap(setA, setB) {
  if (!setA || !setB) return false;
  var a = setA.toLowerCase().split(',').map(function(e) { return e.trim(); });
  var b = setB.toLowerCase().split(',').map(function(e) { return e.trim(); });
  return a.some(function(e) { return b.indexOf(e) !== -1; });
}


// ─────────────────────────────────────────────────────────────────────────────
// DATA LOADERS
// ─────────────────────────────────────────────────────────────────────────────

function ae_loadMissionOrg() {
  try {
    var sheet = getTab('MISSION_ORG');
    if (!sheet) return [];
    var data = sheet.getDataRange().getValues();
    if (data.length < 2) return [];
    var headers = data[0].map(function(h) { return String(h).trim(); });
    var rows = [];
    for (var i = 1; i < data.length; i++) {
      var obj = {};
      headers.forEach(function(h, j) { obj[h] = data[i][j]; });
      // Skip explicitly inactive rows
      if (String(obj['Active'] || '').toUpperCase() === 'FALSE') continue;
      rows.push(obj);
    }
    return rows;
  } catch (e) {
    Logger.log('AgentEscalation ae_loadMissionOrg error: ' + e.message);
    return [];
  }
}

/**
 * Returns { areaName: { 'yyyy-MM-dd': true } } for all submissions in DAILY_LOG
 * within the lookback window.
 */
function ae_loadNightlySubmissions(lookbackDays) {
  var tz  = getMissionTimezone();
  var map = {};
  try {
    var sheet = getTab('DAILY_LOG');
    if (!sheet) return map;
    var data = sheet.getDataRange().getValues();
    if (data.length < 2) return map;
    var headers = data[0].map(function(h) { return String(h).trim(); });
    var colDate = headers.indexOf('Date');
    var colArea = headers.indexOf('Area');
    if (colDate === -1 || colArea === -1) return map;

    var cutoffMs = new Date().getTime() - lookbackDays * 86400000;

    for (var i = 1; i < data.length; i++) {
      var raw = data[i][colDate];
      if (!raw) continue;

      // Agent3 writes the Date column as a 'yyyy-MM-dd' STRING. Parsing that with
      // new Date(str) treats it as UTC midnight, which formatDate then shifts back
      // to the PREVIOUS day in the mission's timezone. Read yyyy-MM-dd strings
      // literally so a submission is recorded on the correct day.
      var dateStr, cmpMs;
      var m = String(raw).trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
      if (m) {
        dateStr = m[1] + '-' + m[2] + '-' + m[3];
        cmpMs   = new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10)).getTime();
      } else {
        var d = raw instanceof Date ? raw : new Date(String(raw));
        if (isNaN(d.getTime())) continue;
        dateStr = Utilities.formatDate(d, tz, 'yyyy-MM-dd');
        cmpMs   = d.getTime();
      }
      if (cmpMs < cutoffMs) continue;

      var area = String(data[i][colArea] || '').trim();
      if (!area) continue;
      if (!map[area]) map[area] = {};
      map[area][dateStr] = true;
    }
  } catch (e) {
    Logger.log('AgentEscalation ae_loadNightlySubmissions error: ' + e.message);
  }
  return map;
}

/**
 * Returns { areaNameLower: true } for areas that submitted WEEKLY_FORM_RAW
 * on or after weekKey (the Sunday deadline date).
 *
 * The CCSM weekly form is multi-section — one "¿En qué área sirve?" column
 * repeats once per zone (see CCSM_Agent3.gs a3_parseSectionStructure /
 * fixtures.js) — so every matching column is scanned, not just the first.
 */
function ae_loadWeeklySubmissions(weekKey) {
  var tz  = getMissionTimezone();
  var map = {};
  try {
    var sheet = getTab('WEEKLY_FORM_RAW');
    if (!sheet) return map;
    var data = sheet.getDataRange().getValues();
    if (data.length < 2) return map;
    var headers  = data[0].map(function(h) { return String(h).trim().toLowerCase(); });
    var areaCols = [];
    headers.forEach(function(h, idx) {
      if (h === '¿en qué área sirve?') areaCols.push(idx);
    });
    if (areaCols.length === 0) return map;

    var weekMs = new Date(weekKey + 'T00:00:00').getTime();

    for (var i = 1; i < data.length; i++) {
      var ts = data[i][0]; // Timestamp is always col 0 (Marca temporal)
      if (!(ts instanceof Date) || isNaN(ts.getTime())) continue;
      if (ts.getTime() < weekMs) continue;
      for (var c = 0; c < areaCols.length; c++) {
        var area = String(data[i][areaCols[c]] || '').trim();
        if (area) { map[area.toLowerCase()] = true; break; }
      }
    }
  } catch (e) {
    Logger.log('AgentEscalation ae_loadWeeklySubmissions error: ' + e.message);
  }
  return map;
}


// ─────────────────────────────────────────────────────────────────────────────
// UTILITY HELPERS
// ─────────────────────────────────────────────────────────────────────────────

/** Skip MP rows and Zone=ALL rows (APs without a determinable district). */
function ae_isNonSubmitting(areaObj) {
  if (String(areaObj['Zone'] || '').toUpperCase() === 'ALL') return true;
  if (String(areaObj['Is_MP'] || '').toUpperCase() === 'TRUE') return true;
  return false;
}

/** Returns comma-joined real companion emails, or null if none found. */
function ae_getCompanionEmails(areaObj) {
  var bad = ['notreadyyet', 'tbd@', 'tbd'];
  var emails = ['Companion1_Email', 'Companion2_Email']
    .map(function(col) { return String(areaObj[col] || '').trim(); })
    .filter(function(e) {
      if (!e || e.indexOf('@') === -1) return false;
      var l = e.toLowerCase();
      return !bad.some(function(b) { return l.indexOf(b) !== -1; });
    });
  return emails.length ? emails.join(',') : null;
}

/**
 * Reads an AGENT_CONFIG date key and returns a clean 'yyyy-MM-dd' string.
 * AGENT_CONFIG date cells come back from getValues() as a Date OBJECT, not a
 * string — so a raw String() gives "Mon Jun 08 2026 ..." which breaks lexical
 * date comparisons. This normalizes Date objects, serials, and yyyy-MM-dd text.
 * Returns '' if the key is empty or unparseable.
 */
function ae_cfgDateStr(key) {
  var raw = getConfig(key);
  if (raw === null || raw === undefined || raw === '') return '';
  var tz = getMissionTimezone();
  if (raw instanceof Date) {
    return isNaN(raw.getTime()) ? '' : Utilities.formatDate(raw, tz, 'yyyy-MM-dd');
  }
  var s = String(raw).trim();
  var m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return m[1] + '-' + m[2] + '-' + m[3];
  var d = new Date(s);
  return isNaN(d.getTime()) ? '' : Utilities.formatDate(d, tz, 'yyyy-MM-dd');
}

/**
 * True if the alerts relay is configured, meaning sendEmail('AgentEscalation')
 * will send via UrlFetchApp (relay account quota) instead of MailApp (main
 * account quota). When true, the main-account MailApp quota guard is irrelevant.
 * CCSM's shipped default (see CcsmData.gs AGENT_CONFIG rows) leaves RELAY_2_URL
 * and RELAY_SECRET both blank, so this returns false out of the box.
 */
function ae_relayConfigured() {
  return !!(String(getConfig('RELAY_2_URL') || '').trim() &&
            String(getConfig('RELAY_SECRET') || '').trim());
}

/** Returns 'yyyy-MM-dd' string of the most recent past Sunday (mission timezone). */
function ae_getLastSunday(tz) {
  var now  = new Date();
  var day  = Utilities.formatDate(now, tz, 'EEEE');
  var back = {'Sunday':0,'Monday':1,'Tuesday':2,'Wednesday':3,'Thursday':4,'Friday':5,'Saturday':6}[day] || 0;
  return Utilities.formatDate(new Date(now.getTime() - back * 86400000), tz, 'yyyy-MM-dd');
}

// Spanish weekday/month names — Utilities.formatDate's 'EEEE'/'MMMM' tokens
// always render in English regardless of MISSION_LOCALE (same finding as
// CCSM_Agent1C.gs's A1C_SPANISH_MONTHS, file header note #6, and
// CCSM_Agent3.gs's A3_SPANISH_WEEKDAYS/A3_SPANISH_MONTHS). Index 0 = domingo,
// matching JS Date#getDay().
var AE_SPANISH_WEEKDAYS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
var AE_SPANISH_MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

/** Formats 'yyyy-MM-dd' as 'miércoles, 11 de junio' style for email bodies. */
function ae_fmtDate(dateStr) {
  try {
    var d = new Date(dateStr + 'T12:00:00');
    var tz = getMissionTimezone();
    var weekday = AE_SPANISH_WEEKDAYS[d.getDay()];
    var day = Utilities.formatDate(d, tz, 'd');
    var month = AE_SPANISH_MONTHS[parseInt(Utilities.formatDate(d, tz, 'M'), 10) - 1];
    return weekday + ', ' + day + ' de ' + month;
  } catch (e) { return dateStr; }
}

function ae_escapeHtml(str) {
  return String(str || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/**
 * Removes ESC_ keys older than ESC_KEY_RETENTION_DAYS to prevent
 * PropertiesService bloat. One key per (area, date) means 98 areas at 30 days
 * of nightly-only retention alone approaches ~3,000 keys — a large enough
 * slice of the script-wide 500KB Script Properties budget (shared with the
 * A1A_DATA/A1B_DATA chunked coaching-chain payloads, 50KB+ each) that it was
 * the likely cause of Agent1A's "exceeded the property storage quota" error
 * on 2026-08-03, which killed that week's entire coaching chain before
 * Agent1B/1C ever ran. Dedup only needs to survive MISSED_DAYS_LOOKBACK (3
 * days) for nightly and one week for weekly escalation, so 10 days keeps a
 * comfortable safety margin while cutting steady-state key count ~3x.
 */
var ESC_KEY_RETENTION_DAYS = 10;
function ae_purgeOldKeys() {
  try {
    var tz      = getMissionTimezone();
    var cutoff  = Utilities.formatDate(
      new Date(new Date().getTime() - ESC_KEY_RETENTION_DAYS * 86400000), tz, 'yyyy-MM-dd');
    var props   = PropertiesService.getScriptProperties();
    var all     = props.getProperties();
    var deleted = 0;
    Object.keys(all).forEach(function(key) {
      if (!/^ESC_[NW]_/.test(key)) return;
      var dateStr = key.slice(-10); // last 10 chars = yyyy-MM-dd
      if (dateStr < cutoff) { props.deleteProperty(key); deleted++; }
    });
    if (deleted > 0) Logger.log('AgentEscalation: purged ' + deleted + ' stale key(s).');
  } catch (e) {
    Logger.log('AgentEscalation ae_purgeOldKeys error: ' + e.message);
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// EMAIL BUILDERS (Spanish)
// ─────────────────────────────────────────────────────────────────────────────

function ae_buildNightlyReminderBody(areaName, missedDate, num, formLink) {
  var dateStr = ae_fmtDate(missedDate);
  var urgency = num === 1
    ? 'Este es un recordatorio amistoso de que su informe nocturno no fue enviado en la fecha indicada abajo.'
    : '<strong>Este es su segundo recordatorio.</strong> Su informe nocturno todavía está pendiente. Por favor, envíelo lo antes posible.';
  return ae_wrapHtml([
    '<h2 style="color:#1a4d7c;margin:0 0 12px 0;">' + (num === 1 ? 'Recordatorio de Informe Nocturno' : 'Segundo Recordatorio de Informe Nocturno') + '</h2>',
    '<p>Estimados misioneros de <strong>' + ae_escapeHtml(areaName) + '</strong>,</p>',
    '<p>' + urgency + '</p>',
    '<p><strong>Fecha pendiente:</strong> ' + ae_escapeHtml(dateStr) + '</p>',
    formLink ? ae_linkBtn('Enviar Informe Nocturno', formLink) : '',
    ae_footer(),
  ]);
}

function ae_buildNightlyEscalationBody(areaName, missedDate, formLink) {
  var dateStr = ae_fmtDate(missedDate);
  return ae_wrapHtml([
    '<h2 style="color:#b91c1c;margin:0 0 12px 0;">Informe Nocturno Faltante — Seguimiento Necesario</h2>',
    '<p>Esta es una alerta automática de <strong>PMG Compass</strong>.</p>',
    '<p>El área <strong>' + ae_escapeHtml(areaName) + '</strong> no ha enviado su informe nocturno ' +
      'correspondiente al <strong>' + ae_escapeHtml(dateStr) + '</strong>.</p>',
    '<p>Ya se han enviado dos recordatorios a los misioneros. Por favor, comuníquese directamente ' +
      'con ellos y anímelos a enviarlo.</p>',
    formLink ? '<p><strong>Enlace del formulario:</strong> <a href="' + ae_escapeHtml(formLink) + '" style="color:#1a4d7c;">' +
      ae_escapeHtml(formLink) + '</a></p>' : '',
    ae_footer(),
  ]);
}

function ae_buildWeeklyReminderBody(areaName, weekKey, num, formLink) {
  var dateStr = ae_fmtDate(weekKey);
  var urgency = num === 1
    ? 'Este es un recordatorio de que su informe semanal aún no ha sido enviado.'
    : '<strong>Este es su segundo recordatorio.</strong> Su informe semanal todavía está pendiente. Por favor, envíelo lo antes posible.';
  return ae_wrapHtml([
    '<h2 style="color:#1a4d7c;margin:0 0 12px 0;">' + (num === 1 ? 'Recordatorio de Informe Semanal' : 'Segundo Recordatorio de Informe Semanal') + '</h2>',
    '<p>Estimados misioneros de <strong>' + ae_escapeHtml(areaName) + '</strong>,</p>',
    '<p>' + urgency + '</p>',
    '<p><strong>Semana que terminó el:</strong> ' + ae_escapeHtml(dateStr) + ' (domingo)</p>',
    formLink ? ae_linkBtn('Enviar Informe Semanal', formLink) : '',
    ae_footer(),
  ]);
}

function ae_buildWeeklyEscalationBody(areaName, weekKey, formLink) {
  var dateStr = ae_fmtDate(weekKey);
  return ae_wrapHtml([
    '<h2 style="color:#b91c1c;margin:0 0 12px 0;">Informe Semanal Faltante — Seguimiento Necesario</h2>',
    '<p>Esta es una alerta automática de <strong>PMG Compass</strong>.</p>',
    '<p>El área <strong>' + ae_escapeHtml(areaName) + '</strong> no ha enviado su informe semanal ' +
      'correspondiente a la semana que terminó el <strong>' + ae_escapeHtml(dateStr) + '</strong>.</p>',
    '<p>Ya se han enviado dos recordatorios a los misioneros. Por favor, comuníquese directamente ' +
      'con ellos y anímelos a enviarlo.</p>',
    formLink ? '<p><strong>Enlace del formulario:</strong> <a href="' + ae_escapeHtml(formLink) + '" style="color:#1a4d7c;">' +
      ae_escapeHtml(formLink) + '</a></p>' : '',
    ae_footer(),
  ]);
}

function ae_wrapHtml(lines) {
  return '<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333333;' +
    'max-width:640px;margin:0 auto;padding:20px;">' +
    lines.filter(Boolean).join('\n') + '</body></html>';
}

function ae_linkBtn(label, url) {
  return '<p style="margin-top:20px;"><a href="' + ae_escapeHtml(url) + '" ' +
    'style="background:#1a4d7c;color:#ffffff;padding:10px 20px;text-decoration:none;' +
    'border-radius:4px;font-weight:bold;display:inline-block;">' +
    ae_escapeHtml(label) + '</a></p>';
}

function ae_footer() {
  return '<p style="color:#6b7280;font-size:12px;margin-top:32px;border-top:1px solid #e5e7eb;' +
    'padding-top:12px;">— PMG Compass (' + getMissionName() + ')</p>';
}


// ─────────────────────────────────────────────────────────────────────────────
// TEST RESET
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Clears stored escalation stages for ONE area so you can re-fire its reminders
 * — e.g. to confirm relay delivery. Edit AREA, and optionally DATE_ONLY.
 *   DATE_ONLY = ''            → clears ALL missing-date stages for the area
 *   DATE_ONLY = '2026-06-08'  → clears ONLY that date's stage (safer; leaves any
 *                               other in-flight dates at their current stage)
 * Run, then run runNightlyEscalation. Affects only this area.
 */
function resetAreaEscalation() {
  var AREA      = 'Los Huertos';       // ← edit to your test area
  var DATE_ONLY = '';                  // ← '' = all dates, or one yyyy-MM-dd

  var props = PropertiesService.getScriptProperties();
  var all   = props.getProperties();
  var deleted = 0;
  Object.keys(all).forEach(function(k) {
    var isArea = (k.indexOf('ESC_N_' + AREA + '_') === 0 || k.indexOf('ESC_W_' + AREA + '_') === 0);
    if (!isArea) return;
    if (DATE_ONLY && k.slice(-10) !== DATE_ONLY) return;   // scope to one date if set
    props.deleteProperty(k);
    Logger.log('  deleted ' + k + ' (was ' + all[k] + ')');
    deleted++;
  });
  Logger.log('resetAreaEscalation: cleared ' + deleted + ' stage key(s) for "' + AREA + '"' +
    (DATE_ONLY ? ' on ' + DATE_ONLY : ' (all dates)') + '.');
  Logger.log('Now run runNightlyEscalation (TEST_AREA_ONLY=' + AREA + ') to re-fire.');
}


// ─────────────────────────────────────────────────────────────────────────────
// AUDIT LOG
// ─────────────────────────────────────────────────────────────────────────────

function ae_logAudit(action, area, reference, sentTo) {
  try {
    var sheet = getTab('AUDIT_LOG');
    if (!sheet) return;
    sheet.appendRow([
      Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd HH:mm:ss'),
      'AgentEscalation',
      action,
      1,
      area,
      reference + ' → ' + sentTo
    ]);
  } catch (e) {
    Logger.log('ae_logAudit error: ' + e.message);
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// TEST / DRY RUN
// ─────────────────────────────────────────────────────────────────────────────

/**
 * BLAST-RADIUS PREVIEW for the nightly escalation. Runs the EXACT same logic as
 * runNightlyEscalation() but SENDS NOTHING and CHANGES NOTHING. Reports how many
 * areas would get each action and the total emails it would send — so you can
 * see the impact before running it for real.
 * Run manually from the editor and read the Execution log.
 */
function previewNightlyEscalation() {
  var tz  = getMissionTimezone();
  var now = new Date();
  var today   = Utilities.formatDate(now, tz, 'yyyy-MM-dd');
  var todayMs = new Date(today + 'T00:00:00').getTime();

  var missionOrg  = ae_loadMissionOrg();
  var lookback    = Math.max(4, parseInt(getConfig('MISSED_DAYS_LOOKBACK') || '14', 10));
  var systemStart = ae_cfgDateStr('SYSTEM_START_DATE');
  var submitted   = ae_loadNightlySubmissions(lookback);
  var allProps    = PropertiesService.getScriptProperties().getProperties();

  var r1 = [], r2 = [], esc = [], noEmail = [], nonSub = [];
  var totalEmails = 0;

  missionOrg.forEach(function(areaObj) {
    var areaName = String(areaObj['Area_Name'] || '').trim();
    if (ae_isNonSubmitting(areaObj)) { nonSub.push(areaName); return; }
    var companions = ae_getCompanionEmails(areaObj);
    if (!areaName || !companions) { noEmail.push(areaName); return; }

    var areaSub = submitted[areaName] || {};
    for (var d = 2; d <= lookback; d++) {
      var missedMs   = todayMs - d * 86400000;
      var missedDate = Utilities.formatDate(new Date(missedMs), tz, 'yyyy-MM-dd');
      if (systemStart && missedDate < systemStart) continue;
      if (areaSub[missedDate]) continue;

      var stage = allProps['ESC_N_' + areaName + '_' + missedDate] || '0';
      if (stage === 'DONE' || stage === '3') continue;

      if (d >= 4 && stage === '2')      { esc.push(areaName + ' (' + missedDate + ')'); totalEmails++; }
      else if (d >= 3 && stage === '1') { r2.push(areaName + ' (' + missedDate + ')');  totalEmails++; }
      else if (d >= 2 && stage === '0') { r1.push(areaName + ' (' + missedDate + ')');  totalEmails++; }
    }
  });

  Logger.log('=== previewNightlyEscalation (NO emails sent) ===');
  Logger.log('Today: ' + today + '  |  SYSTEM_START_DATE: ' + systemStart + '  |  lookback: ' + lookback + 'd');
  Logger.log('Active areas evaluated: ' + missionOrg.length);
  Logger.log('');
  Logger.log('WOULD SEND ' + totalEmails + ' email(s) total:');
  Logger.log('  Reminder 1 → companions:  ' + r1.length);
  Logger.log('  Reminder 2 → companions:  ' + r2.length);
  Logger.log('  Escalation → DL/ZL:       ' + esc.length);
  Logger.log('');
  Logger.log('Skipped — no valid email:   ' + noEmail.length);
  Logger.log('Skipped — leadership/AP/MP: ' + nonSub.length);
  Logger.log('');
  if (r1.length)  Logger.log('Reminder 1 areas: ' + r1.join(', '));
  if (r2.length)  Logger.log('Reminder 2 areas: ' + r2.join(', '));
  if (esc.length) Logger.log('Escalation areas: ' + esc.join(', '));
  if (noEmail.length) Logger.log('No-email areas: ' + noEmail.join(', '));
  Logger.log('=== END preview ===');
}

/**
 * BLAST-RADIUS PREVIEW for the weekly escalation. Same as above but for the
 * weekly form chain. Sends nothing, changes nothing.
 */
function previewWeeklyEscalation() {
  var tz      = getMissionTimezone();
  var now     = new Date();
  var dayName = Utilities.formatDate(now, tz, 'EEEE');
  var stageForDay = {'Monday': 1, 'Tuesday': 2, 'Wednesday': 3}[dayName];

  var weekKey     = ae_getLastSunday(tz);
  var systemStart = ae_cfgDateStr('SYSTEM_START_DATE');

  Logger.log('=== previewWeeklyEscalation (NO emails sent) ===');
  Logger.log('Today: ' + dayName + ' (' + Utilities.formatDate(now, tz, 'yyyy-MM-dd') + ')  |  week deadline: ' + weekKey);

  if (!stageForDay) {
    Logger.log('Weekly system only runs Mon–Wed. Today is ' + dayName + ' → 0 actions.');
    Logger.log('=== END preview ==='); return;
  }
  if (systemStart && weekKey < systemStart) {
    Logger.log('week deadline ' + weekKey + ' is before SYSTEM_START_DATE ' + systemStart + ' → 0 actions (whole run skipped).');
    Logger.log('=== END preview ==='); return;
  }

  var missionOrg = ae_loadMissionOrg();
  var submitted  = ae_loadWeeklySubmissions(weekKey);
  var allProps   = PropertiesService.getScriptProperties().getProperties();
  var stageLabel = {1: 'Reminder 1', 2: 'Reminder 2', 3: 'Escalation → DL'}[stageForDay];

  var willSend = [], noEmail = [], nonSub = [], submittedOk = [], notReady = [];

  missionOrg.forEach(function(areaObj) {
    var areaName = String(areaObj['Area_Name'] || '').trim();
    if (ae_isNonSubmitting(areaObj)) { nonSub.push(areaName); return; }
    var companions = ae_getCompanionEmails(areaObj);
    if (!areaName || !companions) { noEmail.push(areaName); return; }
    if (submitted[areaName.toLowerCase()]) { submittedOk.push(areaName); return; }

    var stage = parseInt(allProps['ESC_W_' + areaName + '_' + weekKey] || '0', 10);
    if (stage >= stageForDay || stage !== stageForDay - 1) { notReady.push(areaName + ' (stage ' + stage + ')'); return; }
    willSend.push(areaName);
  });

  Logger.log('Today\'s stage: ' + stageLabel);
  Logger.log('WOULD SEND ' + willSend.length + ' × ' + stageLabel);
  Logger.log('Already submitted this week: ' + submittedOk.length);
  Logger.log('Not at the right stage yet:  ' + notReady.length);
  Logger.log('Skipped — no valid email:    ' + noEmail.length);
  Logger.log('Skipped — leadership/AP/MP:  ' + nonSub.length);
  if (willSend.length) Logger.log('Would send to: ' + willSend.join(', '));
  Logger.log('=== END preview ===');
}

/**
 * Pinpoint diagnostic for ONE area — explains exactly why the nightly escalation
 * did or did not send a reminder. Edit AREA below to your test area, then Run.
 * Sends no email and changes nothing. Read the Execution log for the trace.
 */
function debugNightlyArea() {
  var AREA = 'Los Huertos';   // ← edit to your test area

  var tz  = getMissionTimezone();
  var now = new Date();
  var today   = Utilities.formatDate(now, tz, 'yyyy-MM-dd');
  var todayMs = new Date(today + 'T00:00:00').getTime();

  Logger.log('=== debugNightlyArea: "' + AREA + '" ===');
  Logger.log('Today: ' + today);
  Logger.log('SYSTEM_START_DATE (normalized): "' + ae_cfgDateStr('SYSTEM_START_DATE') + '"');

  // 1. MISSION_ORG presence + eligibility
  var missionOrg = ae_loadMissionOrg();
  var areaObj = null;
  missionOrg.forEach(function(o) {
    if (String(o['Area_Name'] || '').trim() === AREA) areaObj = o;
  });
  if (!areaObj) {
    Logger.log('NOT FOUND in MISSION_ORG (active rows). Exact Area_Name mismatch?');
    // list near-matches
    missionOrg.forEach(function(o) {
      var n = String(o['Area_Name'] || '').trim();
      if (n.toLowerCase().indexOf(AREA.toLowerCase().slice(0, 6)) !== -1) Logger.log('  candidate: "' + n + '"');
    });
    return;
  }
  Logger.log('Found in MISSION_ORG. Zone="' + areaObj['Zone'] + '" District="' + areaObj['District'] + '"');
  Logger.log('isNonSubmitting (Zone=ALL or Is_MP): ' + ae_isNonSubmitting(areaObj));
  Logger.log('Companion1_Email="' + areaObj['Companion1_Email'] + '" Companion2_Email="' + areaObj['Companion2_Email'] + '"');
  Logger.log('Resolved companions: ' + ae_getCompanionEmails(areaObj));

  // 2. What submission dates does DAILY_LOG show for this area?
  var lookback  = Math.max(4, parseInt(getConfig('MISSED_DAYS_LOOKBACK') || '14', 10));
  var submitted = ae_loadNightlySubmissions(lookback);
  var areaSub   = submitted[AREA] || {};
  Logger.log('DAILY_LOG submission dates seen for this area: ' +
    (Object.keys(areaSub).length ? Object.keys(areaSub).sort().join(', ') : '(none)'));

  // 3. Current PropertiesService stages for this area
  var allProps = PropertiesService.getScriptProperties().getProperties();
  var mine = Object.keys(allProps).filter(function(k) { return k.indexOf('ESC_N_' + AREA + '_') === 0; });
  Logger.log('Existing ESC_N stages: ' + (mine.length ? mine.map(function(k){return k.slice(-10)+'='+allProps[k];}).join(', ') : '(none)'));

  // 4. Per-day decision trace
  var systemStart = ae_cfgDateStr('SYSTEM_START_DATE');
  Logger.log('--- per-day decision (d = days before today) ---');
  for (var d = 1; d <= Math.min(lookback, 8); d++) {
    var missedMs   = todayMs - d * 86400000;
    var missedDate = Utilities.formatDate(new Date(missedMs), tz, 'yyyy-MM-dd');
    var stage      = allProps['ESC_N_' + AREA + '_' + missedDate] || '0';
    var verdict;
    if (d < 2) verdict = 'SKIP: too recent (reminders start at d=2)';
    else if (systemStart && missedDate < systemStart) verdict = 'SKIP: before SYSTEM_START_DATE';
    else if (areaSub[missedDate]) verdict = 'SKIP: form WAS submitted this date';
    else if (stage === 'DONE' || stage === '3') verdict = 'SKIP: stage=' + stage + ' (done/escalated)';
    else if (d >= 4 && stage === '2') verdict = 'WOULD ESCALATE to leader';
    else if (d >= 3 && stage === '1') verdict = 'WOULD SEND Reminder 2';
    else if (d >= 2 && stage === '0') verdict = 'WOULD SEND Reminder 1  ◄◄◄';
    else verdict = 'no-op (stage=' + stage + ', d=' + d + ')';
    Logger.log('  d=' + d + '  ' + missedDate + '  stage=' + stage + '  → ' + verdict);
  }
  Logger.log('=== END debugNightlyArea ===');
}

/**
 * Dry run — logs what the system would do without sending any emails or
 * modifying PropertiesService. Run manually from the Apps Script editor.
 */
function testEscalation() {
  Logger.log('=== AgentEscalation DRY RUN ===');
  var tz = getMissionTimezone();

  var missionOrg = ae_loadMissionOrg();
  Logger.log('MISSION_ORG rows loaded: ' + missionOrg.length);

  // Nightly submissions
  var lookback  = parseInt(getConfig('MISSED_DAYS_LOOKBACK') || '14', 10);
  var submitted = ae_loadNightlySubmissions(lookback);
  Logger.log('Areas with nightly submissions (last ' + lookback + ' days): ' + Object.keys(submitted).length);

  // Weekly submissions
  var weekKey   = ae_getLastSunday(tz);
  var wkSubmit  = ae_loadWeeklySubmissions(weekKey);
  Logger.log('Last Sunday (weekly deadline): ' + weekKey);
  Logger.log('Areas submitted weekly form this week: ' + Object.keys(wkSubmit).length);

  // Full escalation routing audit — all areas
  Logger.log('--- Escalation routing (all areas) ---');
  var noEscalation = [];
  var selfEscalation = [];
  var ok = 0;

  missionOrg.forEach(function(areaObj) {
    if (ae_isNonSubmitting(areaObj)) return;
    var areaName   = String(areaObj['Area_Name'] || '?').trim();
    var companions = ae_getCompanionEmails(areaObj);
    var escEmail   = ae_getEscalationEmail(areaObj, missionOrg);

    var role = '';
    if (String(areaObj['Is_DL'] || '').toUpperCase() === 'TRUE') role = '[DL]';
    else if (String(areaObj['Is_ZL'] || '').toUpperCase() === 'TRUE') role = '[ZL]';
    else if (String(areaObj['Is_STL'] || '').toUpperCase() === 'TRUE') role = '[STL]';

    if (!escEmail) {
      noEscalation.push(areaName + ' ' + role);
      Logger.log('  NO_ESC  ' + role + ' ' + areaName + ' (district="' + (areaObj['District'] || '') + '" zone="' + (areaObj['Zone'] || '') + '")');
    } else if (companions && ae_emailsOverlap(escEmail, companions)) {
      // Should never reach here after the guard, but flag if it does
      selfEscalation.push(areaName + ' ' + role);
      Logger.log('  SELF_ESC ' + role + ' ' + areaName + ' → ' + escEmail);
    } else {
      ok++;
      Logger.log('  ok      ' + role + ' ' + areaName + ' → ' + escEmail);
    }
  });

  Logger.log('--- Summary ---');
  Logger.log('Routing OK:         ' + ok);
  Logger.log('No escalation path: ' + noEscalation.length + (noEscalation.length ? ' → ' + noEscalation.join(', ') : ''));
  Logger.log('Self-escalation:    ' + selfEscalation.length + (selfEscalation.length ? ' → ' + selfEscalation.join(', ') : ''));

  // Current PropertiesService state
  var allProps = PropertiesService.getScriptProperties().getProperties();
  var escKeys  = Object.keys(allProps).filter(function(k) { return /^ESC_[NW]_/.test(k); });
  Logger.log('--- Current escalation state (' + escKeys.length + ' key(s)) ---');
  escKeys.slice(0, 20).forEach(function(k) { Logger.log('  ' + k + ' = ' + allProps[k]); });
  if (escKeys.length > 20) Logger.log('  ... (' + (escKeys.length - 20) + ' more)');

  Logger.log('=== END DRY RUN ===');
}
