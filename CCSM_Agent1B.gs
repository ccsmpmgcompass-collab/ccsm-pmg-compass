/**
 * ============================================================
 * CCSM_Agent1B.gs — Sunday Coaching: Message Selection
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of Agent1B.gs (docs/Agent1B.gs in PMG-Compass) for the CCSM Spanish
 * form set. Provo's Agent1B reimplemented message-bank loading, metric-key
 * to display-name mapping, and random no-repeat selection locally
 * (a1b_loadMessageBank / A1B_METRIC_DISPLAY / a1b_pickMessage /
 * a1b_getLastMsgIds). CCSM_Helpers.gs already ports that exact logic as
 * shared, config-driven functions (getMessageBank / pickMessage /
 * checkNoRepeat) used by every CCSM agent that selects pre-written
 * messages, so this fork calls those instead of re-implementing them —
 * eliminating Provo's English metric-key-to-display-name table entirely
 * (CCSM_Agent1A.gs hands over metric KEYS like 'contact_rate', and
 * MESSAGE_BANK's Metric column is populated with those same keys — see
 * Task 13). checkNoRepeat/pickMessage key off Area_ID (FEEDBACK_HISTORY's
 * schema — see CcsmData.gs), so Agent1A now carries each area's Area_Code
 * through as area.code for this lookup.
 *
 * recordMessageSent() (CCSM_Helpers.gs) is intentionally NOT called here —
 * FEEDBACK_HISTORY is only updated once a message is actually emailed,
 * which happens in Agent1C (Task 8), mirroring Provo's a1c_writeFeedbackHistory.
 *
 * CHAINED FROM: Agent1A (runs ~60 seconds after Agent1A)
 * CHAINS TO:    Agent1C (60 seconds after Agent1B)
 *
 * WHAT IT DOES:
 *   1. Loads area stats saved by Agent1A from Script Properties
 *   2. For each area, picks three messages via CCSM_Helpers.pickMessage()
 *      (random selection from MESSAGE_BANK, filtered by category+metric and
 *      no-repeat against FEEDBACK_HISTORY):
 *        - Strength message 1 (SUNDAY_COACHING_STRENGTH, metric = strength1.key)
 *        - Strength message 2 (SUNDAY_COACHING_STRENGTH, metric = strength2.key)
 *        - Growth message    (SUNDAY_COACHING_GROWTH,    metric = growth.key)
 *   3. Enriches each area entry with the selected message objects (full
 *      MESSAGE_BANK row, looked up via getMessageBank())
 *   4. Saves enriched data back to Script Properties for Agent1C
 *   5. Schedules Agent1C in 60 seconds
 *
 * HARD RULE (enforced in CCSM_Helpers.gs pickMessage()): message selection
 * is plain random-with-no-repeat — Gemini is NEVER called here, and never
 * generates message text. All message text is pre-written and stored in
 * MESSAGE_BANK (Task 13).
 */

// ─── MAIN ENTRY POINT ────────────────────────────────────────────────────────

function runAgent1B() {
  var status = 'SUCCESS';
  var notes  = [];

  try {
    Logger.log('Agent1B: Starting message selection — ' + new Date().toISOString());

    // Load Agent1A's output. loadTempData() already parses the JSON it
    // stored, so payload is the object saveTempData('A1A_DATA', {...}) saved.
    var payload = loadTempData('A1A_DATA');
    if (!payload) throw new Error('A1A_DATA not found in Script Properties. Did Agent1A run?');

    var areaCount = 0;
    var msgCount  = 0;

    Object.keys(payload.areas).forEach(function(areaName) {
      var area     = payload.areas[areaName];
      var areaKey  = area.code || areaName; // FEEDBACK_HISTORY keys off Area_ID

      if (area.strength1) {
        area.msg_strength1 = a1b_pickAndAttach(areaKey, 'SUNDAY_COACHING_STRENGTH', area.strength1.key);
        if (area.msg_strength1) msgCount++;
      }

      if (area.strength2) {
        area.msg_strength2 = a1b_pickAndAttach(areaKey, 'SUNDAY_COACHING_STRENGTH', area.strength2.key);
        if (area.msg_strength2) msgCount++;
      }

      if (area.growth) {
        area.msg_growth = a1b_pickAndAttach(areaKey, 'SUNDAY_COACHING_GROWTH', area.growth.key);
        if (area.msg_growth) msgCount++;
      }

      areaCount++;
    });

    notes.push('Messages selected for ' + areaCount + ' areas (' + msgCount + ' messages)');

    // Release A1A_DATA BEFORE writing A1B_DATA.
    //
    // `payload` is already fully in memory, so the stored copy is dead weight
    // from here on — but saveTempData() only clears the key it is writing, so
    // without this both payloads are resident at the moment A1B_DATA is
    // written. Measured against real 43-area data that is 364KB + 426KB
    // against Apps Script's script-wide 500KB Script Properties quota, and
    // Agent1B died with "You have exceeded the property storage quota" every
    // time — which is what killed the whole coaching chain on 2026-08-03 and
    // why Agent1C had never once run. Clearing here keeps the peak at one
    // payload instead of two. Agent1C still clears both at the end for the
    // normal case.
    saveTempData('A1A_DATA', '');

    saveTempData('A1B_DATA', payload);
    scheduleNext('runAgent1C', 1);
    notes.push('Agent1C scheduled in ~1 min');
    Logger.log('Agent1B: Complete — ' + notes.join(' | '));

  } catch (e) {
    status = 'ERROR';
    notes.push('ERROR: ' + e.message);
    Logger.log('Agent1B FATAL: ' + e.message + '\n' + (e.stack || ''));
  }

  // logRun(agent, status, recordsProcessed, emailsSent, durationMs, notes, error)
  logRun('Agent1B', status, null, null, null, notes.join(' | '));
}

// ─── MESSAGE SELECTION ──────────────────────────────────────────────────────

/**
 * Picks a Message_ID via CCSM_Helpers.pickMessage() (random, no-repeat
 * against FEEDBACK_HISTORY — see CCSM_Helpers.gs's HARD RULE: Gemini never
 * generates or is even consulted for this text) and returns the FULL
 * MESSAGE_BANK row for that ID via CCSM_Helpers.getMessageBank(), so
 * Agent1C (Task 8) has the subject/body/PMG/scripture text ready without a
 * second sheet read. Returns null if no active MESSAGE_BANK row exists for
 * this category+metric.
 */
function a1b_pickAndAttach(areaKey, category, metricKey) {
  var messageId = pickMessage(areaKey, category, metricKey);
  if (!messageId) return null;

  var candidates = getMessageBank(category, metricKey);
  for (var i = 0; i < candidates.length; i++) {
    if (candidates[i].messageId === messageId) return candidates[i];
  }
  // Should not happen (pickMessage only returns IDs it just read from this
  // same pool), but never surface a bare ID with no message record.
  return { messageId: messageId };
}
