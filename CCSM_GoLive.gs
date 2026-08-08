/**
 * ============================================================
 * CCSM_GoLive.gs — the two go-live config switches
 * PMG Compass | Chile Concepción South Mission (CCSM)
 * ============================================================
 *
 * Moments that change what this system does to real people:
 *
 *   STEP A     — 2026-08-05, the leadership trial. Real mail starts, but only
 *                to leaders. 45 of the 98 MISSION_ORG rows carry a leader flag.
 *   STEP ZONES — 2026-08-10, a 4-zone phased rollout (San Pedro, Los Angeles
 *                Norte, Angol, Temuco Ñielol — ~42 of 98 rows). Neither
 *                LEADERS nor ALL fits a named subset of zones, so this scope
 *                reads MISSION_ORG.Zone directly.
 *   STEP B     — 2026-08-17, mission-wide launch. All 98 areas.
 *
 * WHY THIS IS A SCRIPT AND NOT A HAND EDIT
 * Step A sets 98 MISSION_ORG.Active booleans conditionally on five leader
 * flags, and Step B reverses all 98. Done by hand on the morning of, that is
 * where a mistake lives — and the mistake is either mass-mailing the whole
 * mission during a leadership-only trial, or silencing the leaders it exists
 * to test.
 *
 * WHY IT IS NOT ON A TIME TRIGGER
 * TEST_MODE -> FALSE is the one irreversible flip: the moment agent mail
 * reaches real missionaries. Its go/no-go depends on something no scheduled
 * job can evaluate — whether mail is actually being delivered. A trigger
 * firing at 00:01 on Aug 5 would flip it whether or not the relay was ever
 * configured, and that failure is silent: mail just stops. So goLiveApplyStepA
 * REFUSES to run unless the relay checks below pass.
 *
 * HOW TO RUN, on the day:
 *   1. Apps Script editor -> Run -> goLiveDryRunStepA   (writes NOTHING)
 *   2. Read the log. Every change is listed as before -> after.
 *   3. Run -> goLiveApplyStepA
 *   4. Run -> smokeTestPipeline  (CCSM_Setup.gs) to confirm the system is sane
 *
 * Same four steps for Step Zones (goLiveDryRunStepZones / goLiveApplyStepZones)
 * on 2026-08-10, and for Step B on 2026-08-17.
 *
 * Every function here is zero-argument (Apps Script's Run menu cannot pass
 * arguments) and idempotent — running apply twice is a no-op the second time.
 */

// ─── THE STEPS, AS DATA ───────────────────────────────────────────────────────

/** Leader flags in MISSION_ORG. A row is a "leader row" if ANY is TRUE. */
var GOLIVE_LEADER_FLAGS = ['Is_DL', 'Is_ZL', 'Is_STL', 'Is_AP', 'Is_MP'];

/**
 * Step A — 2026-08-05, leadership trial.
 *
 * SYSTEM_START_DATE is what stops "you missed Aug 1/2/3/4" reaching anyone:
 * CCSM_AgentEscalation and CCSM_AgentReminder both skip dates before it, for
 * missed-days AND weekly compliance, so this one field covers both.
 *
 * TRANSFER_START_DATE is deliberately NOT touched. It drives "since transfer"
 * cumulative stats, a separate concern from compliance nagging, and there is
 * no data before Aug 5 for an earlier date to distort.
 */
var GOLIVE_STEP_A = {
  name:            'STEP A — leadership trial',
  date:            '2026-08-05',
  testMode:        'FALSE',
  systemStartDate: '2026-08-05',
  activeScope:     'LEADERS'   // Active=TRUE on leader rows only
};

/**
 * Step Zones — 2026-08-10, phased rollout to 4 named zones only. The other 94
 * rows are left/set inactive. SYSTEM_START_DATE re-baselines to 08-10 for the
 * same reason Step A re-baselines to its own date: an area that only started
 * reporting today must not be flagged for "missing" the days before it began.
 *
 * Zone names below are the exact live MISSION_ORG.Zone spelling (matches
 * CCSM_MISSION_ORG_ROWS in CcsmData.gs) — Spanish, with the Ñ. Comparison is
 * still case/whitespace-normalized in golive_isInZones_ as a defensive
 * measure, not because these are expected to drift.
 */
var GOLIVE_ZONE_AUG10_ZONES = ['San Pedro', 'Los Angeles Norte', 'Angol', 'Temuco Ñielol'];
var GOLIVE_STEP_ZONES_AUG10 = {
  name:            'STEP ZONES — 4-zone Aug 10 rollout',
  date:            '2026-08-10',
  testMode:        'FALSE',
  systemStartDate: '2026-08-10',
  activeScope:     'ZONES',
  zones:           GOLIVE_ZONE_AUG10_ZONES
};

/**
 * Step B — 2026-08-17, mission-wide launch. Re-baselines SYSTEM_START_DATE the
 * same way Step A did, so no area is flagged for gaps before the day it
 * actually started.
 */
var GOLIVE_STEP_B = {
  name:            'STEP B — mission-wide launch',
  date:            '2026-08-17',
  testMode:        'FALSE',
  systemStartDate: '2026-08-17',
  activeScope:     'ALL'       // Active=TRUE on every row
};

// ─── PUBLIC ENTRY POINTS (zero-argument, for the Run menu) ───────────────────

function goLiveDryRunStepA()     { return golive_run_(GOLIVE_STEP_A, true); }
function goLiveApplyStepA()      { return golive_run_(GOLIVE_STEP_A, false); }
function goLiveDryRunStepZones() { return golive_run_(GOLIVE_STEP_ZONES_AUG10, true); }
function goLiveApplyStepZones()  { return golive_run_(GOLIVE_STEP_ZONES_AUG10, false); }
function goLiveDryRunStepB()     { return golive_run_(GOLIVE_STEP_B, true); }
function goLiveApplyStepB()      { return golive_run_(GOLIVE_STEP_B, false); }

/**
 * Reports whether mail can actually be delivered, without sending anything.
 * Run this before Step A. goLiveApplyStepA runs it too and refuses on failure.
 */
function goLiveCheckRelay() {
  var r = golive_relayReadiness_();
  r.lines.forEach(function(l) { Logger.log(l); });
  Logger.log(r.ok ? 'RELAY READY' : 'RELAY NOT READY — see above');
  return r;
}

// ─── RELAY READINESS ─────────────────────────────────────────────────────────

/**
 * The gate on TEST_MODE -> FALSE.
 *
 * Not merely "is RELAY_2_URL non-blank". Two specific live defects have to be
 * caught here:
 *
 *   1. RELAY_1_URL holds an EMAIL ADDRESS (CCSM.PMG.Relay@gmail.com) where a
 *      Web App URL belongs. It is read by no code path today, so it is inert —
 *      but it is a loaded gun: any future edit that routes an agent through
 *      RELAY_1_URL would hand UrlFetchApp an email address and throw.
 *   2. RELAY_2_URL is blank, and it is the only relay sendEmail() reads.
 *
 * A blank relay is NOT fatal on its own — sendEmail() falls back to MailApp, so
 * mail still goes out. It is fatal at scale: the main consumer Gmail account is
 * capped at 100 recipients/day and Agent1C alone needs 97 for the full roster.
 * So this returns ok=true for a leaders-only trial with no relay (45 sends
 * fits), and ok=false for a mission-wide launch without one.
 *
 * @param {Object} [step] The step being checked (for its .activeScope/.zones),
 *   so recipient count reflects the actual subset of the roster this step
 *   would activate. Omitted (goLiveCheckRelay()'s standalone use) defaults to
 *   the full-roster worst case.
 */
function golive_relayReadiness_(step) {
  var scope = step && step.activeScope;
  var lines = [];
  var problems = [];

  var url1   = String(getConfig('RELAY_1_URL') || '').trim();
  var url2   = String(getConfig('RELAY_2_URL') || '').trim();
  var secret = String(getConfig('RELAY_SECRET') || '').trim();

  function looksLikeWebAppUrl(u) {
    return /^https:\/\/script\.google\.com\/.*\/exec$/.test(u);
  }

  if (url1 && !looksLikeWebAppUrl(url1)) {
    // Warning, not an error: nothing reads RELAY_1_URL today.
    lines.push('  WARN  RELAY_1_URL is not a Web App URL: "' + url1 + '". ' +
               'No code reads it today, so this is inert — but clear it or fix it, ' +
               'because a future routing change would hand this to UrlFetchApp.');
  }

  if (!url2) {
    lines.push('  INFO  RELAY_2_URL is blank. sendEmail() falls back to MailApp, so ' +
               'mail still sends — but every agent then shares this account\'s ' +
               '100 recipients/day.');
  } else if (!looksLikeWebAppUrl(url2)) {
    problems.push('RELAY_2_URL is set but is not a Web App URL ("' + url2 + '"). ' +
                  'It must look like https://script.google.com/macros/s/.../exec — ' +
                  'see CCSM_RelayReceiver.gs for how to deploy one.');
  } else if (!secret) {
    problems.push('RELAY_2_URL is set but RELAY_SECRET is blank. sendEmail() ' +
                  'silently falls back to MailApp in that state, so the relay ' +
                  'would appear configured while spending the main quota.');
  } else {
    lines.push('  OK    RELAY_2_URL and RELAY_SECRET are both set and well-formed.');
  }

  var relayLive = !!(url2 && looksLikeWebAppUrl(url2) && secret);

  // Capacity: how many sends does the roster imply, and does that fit?
  var org = golive_readMissionOrg_();
  var scopedRows;
  if (scope === 'LEADERS') {
    scopedRows = org.rows.filter(function(r) { return golive_isLeader_(r, org.index); });
  } else if (scope === 'ZONES') {
    scopedRows = org.rows.filter(function(r) { return golive_isInZones_(r, org.index, step.zones); });
  } else {
    scopedRows = org.rows;
  }
  var recipients = golive_countAddresses_(scopedRows, org.index);
  lines.push('  INFO  Roster implies ~' + recipients + ' Agent1C recipient(s) for scope ' +
             (scope || 'ALL') + (scope === 'ZONES' ? ' (' + step.zones.join(', ') + ')' : '') + '.');

  if (!relayLive && recipients > 90) {
    problems.push('No relay is configured and this scope needs ~' + recipients +
                  ' emails from Agent1C alone, against a 100/day account limit ' +
                  'shared with Agent3, Agent6 and AgentEscalation. Configure ' +
                  'RELAY_2_URL first, or missionaries will silently receive nothing.');
  }

  problems.forEach(function(p) { lines.push('  ERROR ' + p); });
  return { ok: problems.length === 0, problems: problems, lines: lines,
           relayLive: relayLive, recipients: recipients };
}

// ─── MISSION_ORG HELPERS ─────────────────────────────────────────────────────

function golive_readMissionOrg_() {
  var sheet = getTab('MISSION_ORG');
  var data  = sheet.getDataRange().getValues();
  if (data.length < 2) throw new Error('MISSION_ORG is empty.');

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var index   = {};
  headers.forEach(function(h, i) { index[h] = i; });

  if (index['Active'] === undefined) {
    throw new Error('MISSION_ORG has no "Active" column. Header is: ' + headers.join(' | '));
  }
  var missingFlags = GOLIVE_LEADER_FLAGS.filter(function(f) { return index[f] === undefined; });
  if (missingFlags.length) {
    throw new Error('MISSION_ORG is missing leader-flag column(s): ' + missingFlags.join(', '));
  }

  return { sheet: sheet, headers: headers, index: index, rows: data.slice(1) };
}

/** Sheets stores these as real Booleans OR as the strings TRUE/FALSE depending
 *  on how they were written — see BuildCcsmSheet.gs's ccsmCellsEqual_ for the
 *  same coercion problem. Read both. */
function golive_isTrue_(v) {
  if (v === true) return true;
  return String(v).trim().toUpperCase() === 'TRUE';
}

function golive_isLeader_(row, index) {
  for (var i = 0; i < GOLIVE_LEADER_FLAGS.length; i++) {
    if (golive_isTrue_(row[index[GOLIVE_LEADER_FLAGS[i]]])) return true;
  }
  return false;
}

/** True if the row's Zone column matches one of the given zone names
 *  (case/whitespace-normalized — the values themselves must still be the
 *  live sheet's canonical Spanish spelling; see GOLIVE_ZONE_AUG10_ZONES). */
function golive_isInZones_(row, index, zones) {
  if (index['Zone'] === undefined) return false;
  var rowZone = String(row[index['Zone']] || '').trim().toLowerCase();
  for (var i = 0; i < zones.length; i++) {
    if (rowZone === String(zones[i]).trim().toLowerCase()) return true;
  }
  return false;
}

/** Distinct, sendable companion addresses across the given rows — the same
 *  dedupe Agent1C's people map performs, since areas share one mailbox. */
function golive_countAddresses_(rows, index) {
  var seen = {};
  rows.forEach(function(r) {
    ['Companion1_Email', 'Companion2_Email'].forEach(function(col) {
      if (index[col] === undefined) return;
      var e = String(r[index[col]] || '').trim().toLowerCase();
      if (!e || e.indexOf('@') < 0) return;
      if (e.indexOf('notreadyyet') >= 0 || e.indexOf('tbd@') >= 0) return;
      seen[e] = true;
    });
  });
  return Object.keys(seen).length;
}

// ─── AGENT_CONFIG HELPERS ────────────────────────────────────────────────────

/** Finds a key's 1-based row in AGENT_CONFIG. Returns -1 if absent. */
function golive_configRow_(sheet, key) {
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim() === key) return i + 1;
  }
  return -1;
}

// ─── THE RUNNER ──────────────────────────────────────────────────────────────

/**
 * Computes every change the step implies, logs them as before -> after, and
 * (when dryRun is false) applies them.
 *
 * Writes MISSION_ORG's Active column with ONE setValues() call over the whole
 * column rather than 98 setValue() calls — 98 individual writes is both slow
 * and, more importantly, non-atomic: a mid-way failure would leave the roster
 * in a state that is neither trial nor launch.
 */
function golive_run_(step, dryRun) {
  var mode = dryRun ? 'DRY RUN' : 'APPLY';
  var lines = [];
  function say(s) { lines.push(s); Logger.log(s); }

  say('=== ' + step.name + ' — ' + mode + ' — ' + new Date().toISOString() + ' ===');
  say('Intended effective date: ' + step.date);

  var changes = [];

  // ── 1. Relay / capacity gate ───────────────────────────────────────────────
  var readiness = golive_relayReadiness_(step);
  readiness.lines.forEach(say);

  if (!dryRun && !readiness.ok) {
    say('REFUSING TO APPLY. Flipping TEST_MODE to FALSE now would send agent mail ' +
        'that cannot all be delivered, and the loss is silent. Fix the errors above, ' +
        'then re-run the dry run.');
    return { ok: false, applied: false, changes: [], lines: lines };
  }

  // ── 2. AGENT_CONFIG ────────────────────────────────────────────────────────
  var cfgSheet = getTab('AGENT_CONFIG');
  [['TEST_MODE', step.testMode], ['SYSTEM_START_DATE', step.systemStartDate]].forEach(function(pair) {
    var key = pair[0], want = pair[1];
    var row = golive_configRow_(cfgSheet, key);
    if (row < 0) {
      say('  ERROR AGENT_CONFIG has no "' + key + '" row. Cannot continue.');
      throw new Error('AGENT_CONFIG missing key: ' + key);
    }
    var got = String(cfgSheet.getRange(row, 2).getValue()).trim();
    if (got.toUpperCase() === String(want).toUpperCase()) {
      say('  SAME  AGENT_CONFIG!B' + row + ' ' + key + ' already "' + want + '"');
    } else {
      say('  SET   AGENT_CONFIG!B' + row + ' ' + key + ': "' + got + '" -> "' + want + '"');
      changes.push({ kind: 'config', row: row, key: key, from: got, to: want });
    }
  });

  say('  KEEP  AGENT_CONFIG TRANSFER_START_DATE untouched by design ' +
      '(drives "since transfer" stats, not compliance nagging).');

  // ── 3. MISSION_ORG.Active ──────────────────────────────────────────────────
  var org = golive_readMissionOrg_();
  var activeCol = org.index['Active'] + 1;
  var nameCol   = org.index['Area_Name'];

  var wantByRow = [];
  var flips = { on: [], off: [] };

  org.rows.forEach(function(r, i) {
    var want;
    if (step.activeScope === 'ALL') want = true;
    else if (step.activeScope === 'ZONES') want = golive_isInZones_(r, org.index, step.zones);
    else want = golive_isLeader_(r, org.index);
    var got  = golive_isTrue_(r[org.index['Active']]);
    wantByRow.push([want]);
    if (want !== got) {
      var area = String(r[nameCol] || ('row ' + (i + 2)));
      (want ? flips.on : flips.off).push(area);
    }
  });

  var wantTrue = wantByRow.filter(function(v) { return v[0]; }).length;
  say('  ORG   Active=TRUE on ' + wantTrue + ' of ' + org.rows.length + ' rows after this step ' +
      '(scope ' + step.activeScope + ').');
  if (flips.on.length)  say('  ON    ' + flips.on.length + ' row(s) FALSE->TRUE: ' + flips.on.join(', '));
  if (flips.off.length) say('  OFF   ' + flips.off.length + ' row(s) TRUE->FALSE: ' + flips.off.join(', '));
  if (!flips.on.length && !flips.off.length) say('  SAME  MISSION_ORG.Active already correct for this step.');

  if (flips.on.length || flips.off.length) {
    changes.push({ kind: 'org', on: flips.on.length, off: flips.off.length });
  }

  // A leaders-only step that would silence everyone, or activate everyone, is
  // almost certainly reading the wrong columns. Refuse rather than apply it.
  if (step.activeScope === 'LEADERS' && (wantTrue === 0 || wantTrue === org.rows.length)) {
    say('  ERROR Scope is LEADERS but ' + wantTrue + ' of ' + org.rows.length +
        ' rows would be active. The leader flags are not being read as expected — ' +
        'check the ' + GOLIVE_LEADER_FLAGS.join('/') + ' columns. REFUSING.');
    return { ok: false, applied: false, changes: changes, lines: lines };
  }

  // A zone-scoped step that matches 0 rows almost certainly has a Zone-column
  // spelling mismatch (accents, "Norte" vs "North", a renamed zone). Refuse
  // rather than silently deactivate the entire roster.
  if (step.activeScope === 'ZONES' && wantTrue === 0) {
    say('  ERROR Scope is ZONES (' + step.zones.join(', ') + ') but 0 rows matched. ' +
        'Check MISSION_ORG\'s Zone column spelling against these names exactly. REFUSING.');
    return { ok: false, applied: false, changes: changes, lines: lines };
  }

  // ── 4. Apply ───────────────────────────────────────────────────────────────
  if (dryRun) {
    say('=== DRY RUN — nothing was written. ' + changes.length + ' change group(s) pending. ===');
    return { ok: true, applied: false, changes: changes, lines: lines };
  }

  if (changes.length === 0) {
    say('=== Nothing to do — already in the ' + step.name + ' state. ===');
    return { ok: true, applied: false, changes: [], lines: lines };
  }

  changes.forEach(function(c) {
    if (c.kind === 'config') cfgSheet.getRange(c.row, 2).setValue(c.to);
  });
  if (flips.on.length || flips.off.length) {
    org.sheet.getRange(2, activeCol, wantByRow.length, 1).setValues(wantByRow);
  }

  golive_audit_(step, flips, changes);
  say('=== APPLIED. Run smokeTestPipeline() next. ===');
  return { ok: true, applied: true, changes: changes, lines: lines };
}

/**
 * Records the switch in AUDIT_LOG. Best-effort: a failure to write the audit
 * row must not make the caller think the config change itself failed, since by
 * this point it has already been applied.
 */
function golive_audit_(step, flips, changes) {
  try {
    appendRow('AUDIT_LOG', [
      Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd HH:mm:ss'),
      'GoLive',
      step.name,
      changes.length,
      'Active TRUE<-' + flips.on.length + ' / FALSE<-' + flips.off.length,
      'TEST_MODE=' + step.testMode + ', SYSTEM_START_DATE=' + step.systemStartDate
    ]);
  } catch (e) {
    Logger.log('GoLive: applied successfully, but AUDIT_LOG write failed — ' + e.message);
  }
}
