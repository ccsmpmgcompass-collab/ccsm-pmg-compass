/**
 * ============================================================
 * CCSM_LetterWatchdog.gs — the Monday letters retry themselves
 * PMG Compass | Chile Concepción South Mission (CCSM)
 * ============================================================
 *
 * PLAN-2026-10-13-letter-watchdog.md. On Mon 2026-10-12 Apps Script killed
 * runAgent1A at its 6-minute limit. A killed run runs no catch and writes no
 * AGENT_RUN_LOG row, so nothing noticed, and no letter went out until Zackary
 * re-ran the chain by hand on Tuesday. Agent1C died the same silent way on
 * 28 Sep and 17 Aug.
 *
 * This file notices and restarts it.
 *
 *   - Each step marks LETTER_CHAIN_STATE (CCSM_Helpers.gs letterChainMark_):
 *     running, scheduled, failed or done.
 *   - A check runs 10 minutes after Agent1A starts (runLetterWatchdogRetry,
 *     scheduled by Agent1A), then every 15 minutes until the week's letters
 *     are done. A fixed Monday ~11 PM trigger (runLetterWatchdog) covers an
 *     Agent1A that never started at all.
 *   - A step that is neither done nor plausibly still in flight is restarted
 *     from the furthest step whose input exists. Nothing finished is redone.
 *     Agent1C skips whoever already has the letter (A1C_SENT_<week>), and a
 *     retried Agent1A keeps the week's KI PDF request and its PDFs.
 *   - It keeps trying until Tuesday 09:00 mission time (Zackary, D2). After
 *     that, if the letters still have not gone, it emails
 *     AGENT_CONFIG.LETTER_ALERT_EMAIL once (D3) and stops.
 *
 * Two handler names because CCSM_Helpers.scheduleNext() deletes every trigger
 * of the function it schedules: one name for the fixed weekly trigger, which
 * must survive, and one for the one-shot re-checks.
 *
 * Agent1A needs the same: its restart goes through runAgent1ARetry, never
 * runAgent1A. Until 2026-10-28 it went through runAgent1A, so the 10-19
 * restart deleted the Monday 21:30 trigger and on 10-26 Agent1A never
 * started (AUDIT-2026-10-28-monday-letters.md, A). Every check now also puts
 * that weekly trigger back if it is missing.
 */

// A run older than this is past Apps Script's 6-minute limit: dead.
var LW_RUNNING_MAX_MS   = 7 * 60 * 1000;
// A one-shot trigger fires within a minute or two of its time. Ten minutes
// without the step starting means it never will (17 Aug, 28 Sep).
var LW_SCHEDULED_MAX_MS = 10 * 60 * 1000;
var LW_RECHECK_MIN      = 15;
var LW_STEP_FN          = { '1A': 'runAgent1ARetry', '1B': 'runAgent1B', '1C': 'runAgent1C' };

/** The fixed weekly trigger (CCSM_TRIGGER_SCHEDULE, Monday ~11 PM). */
function runLetterWatchdog() {
  letterWatchdogCheck_(new Date());
}

/** The watchdog's one-shot restart of Agent1A (see the header). */
function runAgent1ARetry() {
  runAgent1A();
}

/**
 * Puts the Monday runAgent1A trigger back when no trigger runs runAgent1A.
 * Returns true when it had to. Never throws: a failed repair must not stop the
 * check that restarts this week's letters.
 */
function lw_ensureWeeklyTrigger_() {
  try {
    if (typeof CCSM_TRIGGER_SCHEDULE === 'undefined') return false;
    var have = ScriptApp.getProjectTriggers().some(function(t) {
      return t.getHandlerFunction() === 'runAgent1A';
    });
    if (have) return false;
    var spec = CCSM_TRIGGER_SCHEDULE.filter(function(s) { return s.fn === 'runAgent1A'; })[0];
    if (!spec) return false;
    installScheduledTrigger_(spec, getMissionTimezone());
    logRun('LetterWatchdog', 'REPAIRED', null, null, null,
           'The weekly runAgent1A trigger was missing -- reinstalled (' + spec.describe + ')');
    return true;
  } catch (e) {
    Logger.log('LetterWatchdog: could not check the runAgent1A trigger -- ' + e.message);
    return false;
  }
}

/** The one-shot re-checks (Agent1A's first one, then the watchdog's own). */
function runLetterWatchdogRetry() {
  letterWatchdogCheck_(new Date());
}

/**
 * One look at the chain, at `now`. Returns what it did, for the tests and the
 * execution log: 'outside' | 'done' | 'in flight' | 'restarted 1A|1B|1C' |
 * 'alerted' | 'gave up'.
 */
function letterWatchdogCheck_(now) {
  var lock = null;
  if (typeof LockService !== 'undefined') {
    lock = LockService.getScriptLock();
    if (!lock.tryLock(30 * 1000)) { Logger.log('LetterWatchdog: another check is running'); return 'busy'; }
  }
  try {
    return lw_check_(now);
  } finally {
    if (lock) lock.releaseLock();
  }
}

function lw_check_(now) {
  lw_ensureWeeklyTrigger_();
  var tz  = getMissionTimezone();
  var win = lw_window_(now, tz);
  var nowStr = Utilities.formatDate(now, tz, 'yyyy-MM-dd HH:mm');
  var st   = letterChainState_();
  var mine = !!(st && st.week === win.weekEnd);

  if (mine && st.step === '1C' && st.state === 'done') {
    deleteTriggerByName('runLetterWatchdogRetry');
    Logger.log('LetterWatchdog: the letters for ' + win.weekEnd + ' went out -- nothing to do');
    return 'done';
  }
  if (nowStr < win.start || nowStr >= win.end) {
    Logger.log('LetterWatchdog: ' + nowStr + ' is outside the letter window for ' + win.weekEnd);
    return 'outside';
  }
  if (nowStr >= win.deadline) {
    return lw_alert_(win.weekEnd, st, mine);
  }

  var age = now.getTime() - ((st && st.at) || 0);
  if (mine && ((st.state === 'running' && age < LW_RUNNING_MAX_MS) ||
               (st.state === 'scheduled' && age < LW_SCHEDULED_MAX_MS))) {
    scheduleNext('runLetterWatchdogRetry', LW_RECHECK_MIN);
    Logger.log('LetterWatchdog: Agent' + st.step + ' ' + st.state + ' ' + Math.round(age / 1000) + ' s ago -- checking again in ' + LW_RECHECK_MIN + ' min');
    return 'in flight';
  }

  var step = lw_restartStep_(win.weekEnd);
  var props = PropertiesService.getScriptProperties();
  var key = 'LETTER_RETRIES_' + win.weekEnd;
  var n = parseInt(props.getProperty(key) || '0', 10) + 1;
  props.setProperty(key, String(n));

  letterChainMark_(win.weekEnd, step, 'scheduled', 'watchdog restart ' + n);
  scheduleNext(LW_STEP_FN[step], 1);
  scheduleNext('runLetterWatchdogRetry', LW_RECHECK_MIN);
  logRun('LetterWatchdog', 'RETRY', null, null, null,
         'Week ' + win.weekEnd + ': ' + lw_describe_(st, mine, age) + ' -- restarted Agent' + step +
         ' (restart ' + n + '; trying until Tuesday 09:00)');
  return 'restarted ' + step;
}

/**
 * The week the letters are for and the window the watchdog acts in, as
 * 'yyyy-MM-dd HH:mm' strings in mission time (string order = time order):
 *   start: Monday 21:00 (Agent1A's trigger aims for ~21:30)
 *   deadline: Tuesday 09:00 (D2: keep trying until Tuesday morning)
 *   end: Wednesday 00:00 (past it, a check is about some other week)
 * The week is the most recent Sunday, the same rule as runAgent1A.
 */
function lw_window_(now, tz) {
  var today = Utilities.formatDate(now, tz, 'yyyy-MM-dd');
  var p = today.split('-');
  var dow = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2])).getUTCDay();
  var weekEnd = lw_addDays_(today, -dow);
  return {
    weekEnd:  weekEnd,
    start:    lw_addDays_(weekEnd, 1) + ' 21:00',
    deadline: lw_addDays_(weekEnd, 2) + ' 09:00',
    end:      lw_addDays_(weekEnd, 3) + ' 00:00'
  };
}

/** 'yyyy-MM-dd' plus n days, in calendar days (no clock, no DST). */
function lw_addDays_(ymd, n) {
  var p = ymd.split('-');
  var d = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + n));
  return d.getUTCFullYear() + '-' + ('0' + (d.getUTCMonth() + 1)).slice(-2) + '-' +
         ('0' + d.getUTCDate()).slice(-2);
}

/**
 * The furthest step whose input is there for this week: Agent1B's payload ->
 * Agent1C, Agent1A's -> Agent1B, neither -> Agent1A. Agent1C clears both when
 * it finishes, so a payload still there means it did not.
 */
function lw_restartStep_(weekEnd) {
  var b = loadTempData('A1B_DATA');
  if (b && b.weekEnd === weekEnd) return '1C';
  var a = loadTempData('A1A_DATA');
  if (a && a.weekEnd === weekEnd) return '1B';
  return '1A';
}

/** What the chain's state says happened, in a sentence for the run log. */
function lw_describe_(st, mine, age) {
  if (!mine) return 'Agent1A never started this week';
  var who = 'Agent' + st.step;
  if (st.state === 'failed')    return who + ' failed: ' + (st.note || 'see its AGENT_RUN_LOG row');
  if (st.state === 'running')   return who + ' started ' + Math.round(age / 60000) + ' min ago and never finished (killed by Apps Script)';
  if (st.state === 'scheduled') return who + ' was scheduled ' + Math.round(age / 60000) + ' min ago and never started';
  return who + ' ' + st.state;
}

/**
 * Tuesday 09:00 and the letters have not gone (D3): one email to
 * LETTER_ALERT_EMAIL, then nothing more for this week.
 */
function lw_alert_(weekEnd, st, mine) {
  deleteTriggerByName('runLetterWatchdogRetry');
  var props = PropertiesService.getScriptProperties();
  var key = 'LETTER_ALERTED_' + weekEnd;
  if (props.getProperty(key)) return 'gave up';
  props.setProperty(key, new Date().toISOString());

  var tries = props.getProperty('LETTER_RETRIES_' + weekEnd) || '0';
  var where = mine ? ('Agent' + st.step + ' ' + st.state + (st.note ? ' (' + st.note + ')' : '')) :
                     'Agent1A never started this week';
  var to = getConfig('LETTER_ALERT_EMAIL');
  if (!to) {
    logRun('LetterWatchdog', 'ERROR', null, 0, null,
           'Week ' + weekEnd + ': the letters did NOT go out (' + where + ', ' + tries +
           ' restart(s)), and nobody was told: AGENT_CONFIG has no LETTER_ALERT_EMAIL.');
    return 'alerted';
  }

  var subject = 'PMG Compass: the weekly letters did NOT go out (week ending ' + weekEnd + ')';
  var html =
    '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#111;max-width:600px;">' +
    '<p><strong>The weekly letters for the week ending ' + weekEnd + ' have not gone out.</strong></p>' +
    '<p>The chain kept restarting itself from Monday night until Tuesday 09:00 and never finished. ' +
    'Restarts: ' + tries + '. Last state: ' + where + '.</p>' +
    '<p><strong>What to do:</strong></p><ol>' +
    '<li>In the Apps Script editor, open <em>Executions</em> and look at the last ' +
    'runAgent1A / runAgent1B / runAgent1C run for its error.</li>' +
    '<li>Once it is fixed, run <code>runAgent1A</code> by hand. The KI PDFs already built are kept, ' +
    'and anyone who already got the letter is skipped, so nobody gets it twice.</li>' +
    '</ol>' +
    '<p style="color:#6b7280;font-size:12px;">Sent by CCSM_LetterWatchdog.gs (PLAN-2026-10-13-letter-watchdog.md).</p>' +
    '</div>';
  try {
    sendEmail(to, subject, html, 'LetterWatchdog');
    logRun('LetterWatchdog', 'ERROR', null, 1, null,
           'Week ' + weekEnd + ': the letters did NOT go out by Tuesday 09:00 (' + where + ', ' +
           tries + ' restart(s)). Alert sent to LETTER_ALERT_EMAIL.');
  } catch (e) {
    logRun('LetterWatchdog', 'ERROR', null, 0, null,
           'Week ' + weekEnd + ': the letters did NOT go out, and the alert failed too: ' + e.message);
  }
  return 'alerted';
}
