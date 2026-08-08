/**
 * CCSM_AddTransferTabs.gs — one-time script to add the 4 tabs Transfer Flow
 * needs to the live COMPASS_CCSM spreadsheet.
 *
 * HOW TO USE
 *   1. Open COMPASS_CCSM in Google Sheets.
 *   2. Extensions > Apps Script.
 *   3. File > New > Script. Name it CCSM_AddTransferTabs (or anything).
 *   4. Delete the placeholder "function myFunction() {}" and paste
 *      everything below in its place.
 *   5. Save (Ctrl+S / the disk icon).
 *   6. Pick "ccsm_buildTransferTabs" from the function dropdown at the top,
 *      click Run. Approve the permissions prompt if it asks (first run
 *      only).
 *   7. Check View > Logs (or Execution log) for a "Created: ..." message.
 *
 * Safe to run more than once — it only creates a tab if it doesn't already
 * exist, and never touches a tab's existing data.
 */
function ccsm_buildTransferTabs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var specs = [
    { name: 'TRANSFER_IMPORT', headers: ['Area', 'Zone', 'District',
        'Companion1_Name', 'Companion2_Name', 'Companion3_Name', 'Companion4_Name',
        'Calling', 'Area_Email'] },
    { name: 'MISSION_ORG_SNAPSHOT', headers: ['Area_Code', 'Area_Name', 'Zone',
        'District', 'Companion1_Name', 'Companion1_Email', 'Companion2_Name',
        'Companion2_Email', 'Is_DL', 'Is_ZL', 'Is_STL', 'Is_AP', 'Is_MP', 'Active'] },
    { name: 'TRANSFER_LOG', headers: ['Timestamp', 'Function', 'Result', 'Details'] },
    { name: 'CLOUD_JOB_STATUS', headers: ['job_id', 'job_type', 'status',
        'progress_text', 'started_at', 'updated_at', 'result_summary'] },
  ];

  var created = [];
  specs.forEach(function(spec) {
    var sheet = ss.getSheetByName(spec.name);
    if (sheet) return;   // already exists — never re-touch an existing tab's data
    sheet = ss.insertSheet(spec.name);
    sheet.getRange(1, 1, 1, spec.headers.length).setValues([spec.headers]);
    sheet.setFrozenRows(1);
    created.push(spec.name);
  });

  Logger.log(created.length
    ? 'Created: ' + created.join(', ')
    : 'All 4 tabs already existed — nothing created.');
}
