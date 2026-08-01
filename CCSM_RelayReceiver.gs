/**
 * CCSM_RelayReceiver.gs — the RELAY_2 web app
 * ------------------------------------------------------------------
 * NOT part of the COMPASS_CCSM bound project. This is a SEPARATE,
 * standalone Apps Script project, deployed as a Web App under a SECOND
 * Gmail account (its own independent 100-email/day Gmail send limit),
 * so Agent1C / Agent3 / Agent6 / AgentEscalation don't all compete for
 * the main CCSM account's quota. See CCSM_Helpers.gs's sendEmail() for
 * the exact request contract this must satisfy — read that first if
 * this file and that comment ever disagree.
 *
 * SETUP
 *   1. Sign in as the SECOND Gmail account (not the main CCSM account).
 *   2. script.google.com -> New project. Rename it "CCSM Relay".
 *   3. Paste this whole file over the starter Code.gs.
 *   4. Gear icon (Project Settings) -> Script Properties -> Add script
 *      property: RELAY_SECRET = <the shared secret you were given>.
 *   5. Deploy -> New deployment -> type "Web app".
 *        Execute as:      Me
 *        Who has access:  Anyone
 *      (must be "Anyone" — the sender calls this anonymously over
 *      UrlFetchApp; the RELAY_SECRET is what protects it, not Google
 *      auth.) Authorize when prompted.
 *   6. Copy the Web app URL from the deployment dialog. Send that URL
 *      back — it goes into COMPASS_CCSM's AGENT_CONFIG as RELAY_2_URL.
 *
 * VERIFY: once RELAY_2_URL and RELAY_SECRET are both filled in
 * AGENT_CONFIG on the COMPASS_CCSM side, run testRelay() there (defined
 * in CCSM_Helpers.gs) — it sends one real email through this relay to
 * TEST_INBOX_EMAIL and logs OK/FAILED.
 */

function doPost(e) {
  var result = { success: false };
  try {
    var data = JSON.parse(e.postData.contents);

    var expected = PropertiesService.getScriptProperties().getProperty('RELAY_SECRET');
    if (!expected) {
      result.error = 'RELAY_SECRET not set on the relay (Script Properties).';
      return jsonOut_(result);
    }
    if (data.secret !== expected) {
      result.error = 'Invalid secret.';
      return jsonOut_(result);
    }
    if (!data.to || !data.subject || !data.body) {
      result.error = 'Missing to/subject/body.';
      return jsonOut_(result);
    }

    MailApp.sendEmail({
      to:       data.to,
      subject:  data.subject,
      htmlBody: data.body,
      replyTo:  data.replyTo || undefined,
      name:     'PMG Compass'
    });
    result.success = true;
  } catch (err) {
    result.error = err.message;
  }
  return jsonOut_(result);
}

function jsonOut_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
