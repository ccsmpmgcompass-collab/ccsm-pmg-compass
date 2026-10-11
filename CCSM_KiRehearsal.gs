/**
 * ============================================================
 * CCSM_KiRehearsal.gs — dress rehearsal for the weekly KI PDFs
 * PMG Compass | Chile Concepción South Mission (CCSM)
 * ============================================================
 *
 * Proves the KI PDF chain (PLAN-2026-10-10-ki-autosend.md) end to end on the
 * live sheet WITHOUT writing to anyone in the mission. Same code as Monday
 * night: Agent1A's WEEKLY_KI rebuild and REQUEST row, the GitHub job, Agent1C's
 * outbox read and recipient rule, sendEmail through the relay. Only the
 * recipient differs: both test emails go to the account running this (or the
 * address passed to step 2).
 *
 * It writes only WEEKLY_KI (rebuilt from the forms, as Agent5A does every day)
 * and KI_PDF_OUTBOX (which Monday's Agent1A clears and rewrites anyway). No
 * letters, no AGENT_RUN_LOG row, no FEEDBACK_HISTORY / WEEKLY_BREAKDOWNS.
 *
 * HOW TO RUN (Apps Script editor, any day but Monday evening):
 *   1. Run rehearseKiPdfsStep1. It rebuilds WEEKLY_KI, creates KI_PDF_OUTBOX
 *      if the job never has, and writes the REQUEST row for REHEARSAL_WEEK_END.
 *   2. GitHub -> Actions -> "Weekly KI PDFs" -> Run workflow, week_end =
 *      REHEARSAL_WEEK_END, leave both boxes unticked. It finds the request,
 *      builds, writes the PDFs (about 2 min). It must go green.
 *   3. Run rehearseKiPdfsStep2. It sends you two emails -- what an AP and what
 *      a zone leader will get, attachments included -- and logs who gets which
 *      PDF on the real roster. Read the execution log for PASS / FAIL.
 *
 * Delete this file from the Apps Script project afterwards (optional; nothing
 * calls it).
 */

// The week the rehearsal grades: the last complete one, already reviewed as
// PDFs. Its cutoff stops before the 11 Oct forms, so a sector filing next
// week's form tonight is not read as a late 4 Oct form (the date-slip rule).
var REHEARSAL_WEEK_END = '2026-10-04';
var REHEARSAL_CUTOFF   = '2026-10-11 00:00:00';

function rehearseKiPdfsStep1() {
  var lines = ['KI REHEARSAL step 1 -- week ending ' + REHEARSAL_WEEK_END];

  // R1: the letter's own rebuild of WEEKLY_KI from WEEKLY_FORM_RAW.
  lines.push(a1a_refreshWeeklyKi_());
  var ki = a1a_loadWeeklyKi(REHEARSAL_WEEK_END, true);
  lines.push('Sectors with a weekly form for ' + REHEARSAL_WEEK_END + ' (date slips included): ' +
             (ki === null ? 'TAB UNAVAILABLE' : Object.keys(ki).length));

  // Agent1A requests only when the tab exists; the job normally creates it.
  var ss = getSpreadsheet();
  if (!ss.getSheetByName(A1A_KI_OUTBOX_TAB)) {
    ss.insertSheet(A1A_KI_OUTBOX_TAB);
    lines.push('Created ' + A1A_KI_OUTBOX_TAB);
  }
  var note = a1a_requestKiPdfs_(REHEARSAL_WEEK_END, REHEARSAL_CUTOFF);
  lines.push(note);
  lines.push(/^KI PDFs requested/.test(note)
    ? 'PASS -- now run the "Weekly KI PDFs" GitHub job with week_end ' + REHEARSAL_WEEK_END +
      ', wait for it to go green, then run rehearseKiPdfsStep2.'
    : 'FAIL -- the request was not written; see the line above.');
  Logger.log(lines.join('\n'));
  return lines;
}

function rehearseKiPdfsStep2(to) {
  to = to || Session.getEffectiveUser().getEmail();
  var lines = ['KI REHEARSAL step 2 -- week ending ' + REHEARSAL_WEEK_END + ', test emails to ' + to];
  var ok = true;

  var kiPdfs = a1c_loadKiPdfs_(REHEARSAL_WEEK_END);
  if (!kiPdfs.requested) {
    lines.push('FAIL -- no REQUEST row for ' + REHEARSAL_WEEK_END + ' in KI_PDF_OUTBOX. Run step 1 first.');
    Logger.log(lines.join('\n'));
    return lines;
  }
  if (!kiPdfs.ready) {
    lines.push('FAIL -- requested, but the job has not written the mission PDF yet. ' +
               'Wait for the GitHub run to go green (it must use week_end ' + REHEARSAL_WEEK_END + ').');
    Logger.log(lines.join('\n'));
    return lines;
  }
  lines.push('Outbox: ' + kiPdfs.docs.length + ' PDFs -- ' + kiPdfs.docs.map(function(d) {
    return d.scope + ' (' + d.pages + ' p, ' + Math.round(d.blob.getBytes().length / 1024) + ' KB)';
  }).join(', '));

  // Who gets what on the real roster, by the rule Agent1C uses.
  var people = a1c_buildPeopleMap(a1c_loadFullMissionOrg());
  var routed = [], ap = null, zl = null;
  Object.keys(people).forEach(function(email) {
    var docs = a1c_kiDocsFor_(people[email], kiPdfs);
    if (!docs.length) return;
    var types = people[email].roles.map(function(r) { return r.type; });
    routed.push({ email: email, name: people[email].name, types: types, docs: docs });
    if (!ap && types.indexOf('AP') >= 0) ap = routed[routed.length - 1];
    if (!zl && types.indexOf('AP') < 0) zl = routed[routed.length - 1];
  });
  lines.push('Letters that will carry PDFs on Monday: ' + routed.length +
             ' (PDFs attached in all: ' + routed.reduce(function(n, r) { return n + r.docs.length; }, 0) + ')');
  routed.forEach(function(r) {
    lines.push('  ' + r.types.join('/') + '  ' + r.name + ' <' + r.email + '>  ' +
               r.docs.map(function(d) { return d.fileName; }).join(', '));
  });
  if (!ap) { ok = false; lines.push('FAIL -- no AP on the roster gets the mission PDF (MISSION_LEADERSHIP?)'); }
  if (!zl) { ok = false; lines.push('FAIL -- no zone leader or STL mailbox gets a zone PDF'); }

  // The two test emails, through the same relay Agent1C uses.
  [ap, zl].forEach(function(r) {
    if (!r) return;
    var role = r.types.indexOf('AP') >= 0 ? 'AP' : 'ZL/STL';
    var body = '<p style="font-family:Arial,sans-serif;font-size:13px;">Ensayo de los adjuntos del ' +
               'correo semanal. En el envío real esto lo recibe <b>' + r.name + '</b> (' + role + '), ' +
               'debajo del encabezado de su carta:</p>' + a1c_kiAttachmentNote_(r.docs, REHEARSAL_WEEK_END);
    var sent = sendEmail(to, '[ENSAYO] Adjuntos KI -- carta de ' + role, body, 'Agent1C',
                         { attachments: r.docs.map(function(d) { return d.blob; }) });
    var got = (sent && typeof sent.attached === 'number') ? sent.attached : 0;
    if (got === r.docs.length) {
      lines.push('Sent the ' + role + ' test email with ' + got + ' attachment(s).');
    } else {
      ok = false;
      lines.push('FAIL -- the ' + role + ' test email went with ' + got + ' of ' + r.docs.length +
                 ' attachments: redeploy CCSM_RelayReceiver.gs (same deployment, new version).');
    }
  });
  if (!a1c_relayConfigured()) {
    lines.push('NOTE -- RELAY_2_URL / RELAY_SECRET not set: these went from the main account, not the relay.');
  }

  lines.push(ok ? 'PASS -- open the two [ENSAYO] emails and check the PDFs open.' : 'FAIL -- see above.');
  Logger.log(lines.join('\n'));
  return lines;
}
