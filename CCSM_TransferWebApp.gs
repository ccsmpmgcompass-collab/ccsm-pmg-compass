// ── CCSM_TransferWebApp.gs ──────────────────────────────────────────────────────
// Headless HTTPS bridge so the CCSM dashboard's Traslados page can trigger the
// nightly + weekly form zone/area dropdown sync WITHOUT anyone opening the
// sheet's Apps Script editor. The gspread service account behind the dashboard
// has NO Forms API access, so form sync must run here.
//
// Ported from Utah Provo's docs/TransferWebApp.gs. Calls CCSM_TransferHelpers.gs
// (cct_getOrgZones_, cct_readFormStructure_, cct_repairFormRouting_,
// cct_cloneItem_, cct_log_) — same Apps Script project = shared global scope.
//
// ── ONE-TIME SETUP (before deploy) ───────────────────────────────────────────
// 1. Set CCT_NIGHTLY_FORM_ID / CCT_WEEKLY_FORM_ID below to CCSM's real form
//    edit IDs — open each Google Form's edit URL
//    (docs.google.com/forms/d/<FORM_ID>/edit) and copy the ID out of it.
//    AGENT_CONFIG's NIGHTLY_FORM_LINK/WEEKLY_FORM_LINK store the published
//    viewform URL, which has a DIFFERENT id — that one will not work here.
// 2. Set CCT_SHARED_SECRET below to a long random string.
//
// ── ONE-TIME DEPLOY ──────────────────────────────────────────────────────────
// 3. Paste this file AND CCSM_TransferHelpers.gs into the COMPASS_CCSM Apps
//    Script project.
// 4. Deploy → New deployment → type "Web app":
//       Execute as:      Me
//       Who has access:  Anyone
//    Copy the /exec URL.
// 5. In dashboard/.streamlit/secrets.toml set:
//       TRANSFER_WEBAPP_URL    = <that /exec URL>
//       TRANSFER_WEBAPP_SECRET = <the same secret as CCT_SHARED_SECRET>
// Re-deploy (Manage deployments → edit → new version) whenever this file changes.

var CCT_SHARED_SECRET = 'CHANGE_ME_to_a_long_random_string';
var CCT_NIGHTLY_FORM_ID = 'CHANGE_ME_nightly_form_edit_id';
var CCT_WEEKLY_FORM_ID = 'CHANGE_ME_weekly_form_edit_id';

function doGet() {
  return cct_json_({ ok: true, service: 'CCSM_TransferWebApp', ts: new Date().toISOString() });
}

function doPost(e) {
  try {
    var body = {};
    if (e && e.postData && e.postData.contents) {
      body = JSON.parse(e.postData.contents);
    }
    if (String(body.secret || '') !== CCT_SHARED_SECRET) {
      return cct_json_({ ok: false, error: 'Unauthorized — bad or missing secret.' });
    }

    var action = String(body.action || '');
    if (action === 'formSync') {
      return cct_formSync_(body.which || 'both');
    }
    return cct_json_({ ok: false, error: 'Unknown action: ' + action });

  } catch (err) {
    return cct_json_({ ok: false, error: String(err && err.message || err) });
  }
}

function cct_formSync_(which) {
  var out = { ok: true };
  which = String(which || 'both').toLowerCase();

  if (which === 'nightly' || which === 'both') {
    out.nightly = cct_applyFormSync_(CCT_NIGHTLY_FORM_ID, 'nightly');
    if (out.nightly.status === 'ERROR') out.ok = false;
  }
  if (which === 'weekly' || which === 'both') {
    out.weekly = cct_applyFormSync_(CCT_WEEKLY_FORM_ID, 'weekly');
    if (out.weekly.status === 'ERROR') out.ok = false;
  }
  return cct_json_(out);
}

function cct_applyFormSync_(formId, label) {
  try {
    var orgZones   = cct_getOrgZones_();
    var formStruct = cct_readFormStructure_(formId);
    var form       = formStruct.form;
    var sections   = formStruct.zoneSections;
    var orgZoneNames = Object.keys(orgZones).sort();

    // Step 1: update area dropdowns in existing sections
    var handledZones = {};
    sections.forEach(function(sec) {
      if (!sec.zoneName) return;
      var key = (sec.zoneName || '').toLowerCase().trim();
      if (orgZones[key]) {
        if (sec.areaItem) sec.areaItem.setChoiceValues(orgZones[key]);
        handledZones[key] = sec.pageBreak;
      } else {
        if (sec.areaItem) sec.areaItem.setChoiceValues(['(No active areas)']);
      }
    });

    // Step 2: add new zone sections
    var templateSec = sections[0];
    orgZoneNames.forEach(function(zoneName) {
      if (handledZones[zoneName]) return;
      var newPb = form.addPageBreakItem().setTitle(zoneName + ' Zone Section');
      form.addListItem()
        .setTitle('What is your area?')
        .setChoiceValues(orgZones[zoneName])
        .setRequired(true);
      templateSec.allSectionItems.slice(2).forEach(function(item) {
        cct_cloneItem_(form, item);
      });
      handledZones[zoneName] = newPb;
    });

    // Step 3: rebuild zone dropdown choices + routing
    var repairResult = cct_repairFormRouting_(formId);

    // Step 4: verification pass
    var verErrors = [];
    if (repairResult.missing.length > 0) {
      verErrors.push('Could not route zones: ' + repairResult.missing.join(', '));
    }

    var status = verErrors.length === 0 ? 'OK' : 'WARN';
    var msg = verErrors.length === 0
      ? label + ' form sync complete. ' + orgZoneNames.length + ' zones verified.'
      : 'Sync applied but verification found issues: ' + verErrors.join(' | ');

    cct_log_('CCSM_TransferWebApp formSync [' + label + ']', status, msg);
    return { status: status, msg: msg };

  } catch (e) {
    cct_log_('CCSM_TransferWebApp formSync [' + label + ']', 'ERROR', e.message);
    return { status: 'ERROR', msg: e.message };
  }
}

function cct_json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
