/**
 * Missionary Daily Report — Google Form builder
 * ------------------------------------------------------------------
 * HOW TO USE
 *   1. Go to https://script.google.com  ->  New project.
 *   2. Delete the sample code, paste THIS ENTIRE FILE in.
 *   3. Run  buildDailyReportForm  (first run: approve the permission prompt).
 *   4. The Execution log prints the form's edit + live URLs and the URL of
 *      the freshly-created linked responses spreadsheet.
 *
 * WHAT IT BUILDS
 *   - Section 1: "What zone are you in?" dropdown. Each zone routes (branches)
 *     to its own section.
 *   - One section per zone: an area dropdown scoped to that zone + the full
 *     nightly question set. Finishing any zone section submits the form.
 *   - Responses are written to a NEW Google Sheet (kept separate from any
 *     live production sheet).
 *
 * SAFE TO RE-RUN: each run creates a brand-new form + sheet; it never edits
 * an existing one.
 *
 * WHY THE VERIFY/FIX PASS: this form creates 200+ items, and Google's Forms
 * Advanced Service intermittently drops a setTitle()/setHelpText() write when
 * many items are created in one run — leaving Google's placeholder text
 * ("Question" / "Description" / "Title"). Sleeps and in-place retries do NOT
 * fix it: getTitle() reads the local pending value, so it can't even detect a
 * dropped server write. Instead, after building, this script RE-OPENS the form
 * by ID (which forces pending writes to flush and returns TRUE server state),
 * then re-applies any titles/help that didn't stick, repeating until a fresh
 * read-back matches. Watch the execution log — it prints how many fixes each
 * round applied and a final "all correct" (or warning) line.
 */

// ==================================================================
// DATA — zones -> areas (source: CurrentOrganization export, cleaned)
// ==================================================================
var ZONES = {
  'San Pedro': ['Boca de la Costa 1', 'Boca de la Costa 2', 'Bosque Mar 1', 'Bosque Mar 2', 'La Marina 1', 'Lomas Coloradas 1', 'Lomas Coloradas 2', 'Los Huertos', 'Oficina 1', 'San Pedro', 'San Pedro 2', 'Santa Juana'],
  'Camilo': ['Camilo Olivarria 1', 'Camilo Olivarria 2', 'Camilo Olivarria 3', 'Coronel', 'Lagunillas 1', 'Lagunillas 2', 'Lota 1', 'Lota 2'],
  'Arauco': ['Arauco 1', 'Arauco 2', 'Cañete 1', 'Cañete 2', 'Curanilahue 1', 'Curanilahue 2', 'Lebu 1', 'Lebu 2', 'Los Alamos'],
  'Los Angeles Norte': ['Almirante Latorre', 'Cabrero 1', 'Cabrero 2', 'Galvarino', 'Galvarino 2', 'Huepil & Tucapel & Villa Obispo', 'Laja 1', 'Laja 2', "Villa O'Higgins", 'Villa Obispo', 'Yumbel'],
  'Los Angeles Sur': ['Av. Alemania', 'Mulchen 1', 'Mulchen 2', 'Nacimiento 1', 'Nacimiento 2', 'San Martin 2', 'San Martín 1', 'Santa Barbara', 'Villa Esmeralda', 'Villa Las Americas 1', 'Villa las Americas 2'],
  'Angol': ['Alemania 1', 'Alemania 2', 'Collipulli', 'El Mirador', 'Huequen', 'Los Confines', 'Los Sauces', 'Tijeral y Renaico'],
  'Victoria': ['Curacautín', 'Perquenco', 'Tolhuaca', 'Traiguen 1', 'Traiguen 2', 'Victoria 1', 'Victoria 2'],
  'Temuco Ñielol': ['Catrihuala 1', 'Catrihuala 2', 'Caupolicán 1', 'Lautaro 1', 'Lautaro 2', 'Lican Ray 1', 'Lican Ray 2', 'Quirihue 1', 'Quirihue 2', 'Vilcun', 'Ñielol 1', 'Ñielol 2'],
  'Temuco Cautín': ['Carahue', 'Cautin 2', 'Cautín 1', 'Cunco', 'Labranza 1', 'Labranza 2', 'Llaima 1', 'Llaima 2', 'Maquehue 1', 'Maquehue 2', 'Nueva Imperial'],
  'Villarrica': ['Ancahual', 'Freire', 'Loncoche', 'MLS Pucón', 'Pitrufquen 1', 'Pitrufquen 2', 'Pucón 1', 'Pucón 2', 'Volcán 1', 'Volcán 2']
};

// ==================================================================
// DATA — the per-area question set, in order.
//   type: 'date' | 'yesno' | 'number' | 'effort' | 'yes'
//   yes  = single "Yes" checkbox (required flag set per item)
// ==================================================================
var QUESTIONS = [
  { type: 'date',   title: 'What date are you inputting?',
    help: "The calendar date of the day you are reporting on. In most cases this will be today's date. If you are catching up from a previous day, enter the date that the numbers actually belong to — not the date you are submitting the form." },

  { type: 'yesno',  title: 'Splits/Exchanges Had',
    help: 'Select Yes if you participated in an approved split or exchange during the day. Select No if you remained with your regular companionship for the entire day.' },

  { type: 'number', title: 'Roleplays Performed Today',
    help: 'The number of roleplays you completed today to practice teaching, finding, or inviting. Count each separate roleplay (scenario), whether done with your companion, leaders, or other missionaries.' },

  { type: 'number', title: 'Non-member Contacts Attempted',
    help: 'Every non-member door you attempted today, whether someone answered or not. If the door stayed closed, it still counts here. This also counts if you are contacting someone in public — it does not have to be at a door.' },

  { type: 'number', title: 'Non-members Contacted',
    help: 'A non-member door that actually opened — someone answered and you made contact. Every contact also counts as a door attempted. This also counts if you are contacting someone in public — it does not have to be at a door.' },

  { type: 'number', title: 'Non-member Meaningful Conversations',
    help: 'A conversation with a non-member that lasted over 3 minutes and included a gospel tie-in. Be honest with yourself — was it truly meaningful? If yes, it also counts as a contact and a door attempted.' },

  { type: 'number', title: 'New People Found',
    help: 'Each person (not baptized) who has received a lesson in a given week (but was not taught in the past three months) and accepted a specific return appointment. A lesson typically includes praying (when appropriate), teaching at least one gospel principle, and extending an invitation.' },

  { type: 'number', title: 'Non-member Lessons',
    help: 'A visit with a non-member where you shared a gospel principle and extended an invitation. Every lesson also counts as a meaningful conversation, a contact, and a door attempted. Lessons should never outnumber meaningful conversations — if they do, recheck your counts.' },

  { type: 'number', title: 'Part Member Families Lessons',
    help: 'A lesson taught in a home where some family members are members of the Church and others are not. Count each lesson as one, even if multiple family members were present.' },

  { type: 'number', title: 'Recent Convert Lessons',
    help: 'Lessons held today with recent converts only. No non-members in this count — it is strictly for recent converts.' },

  { type: 'number', title: 'Recent Convert Lessons Using My Covenant Path',
    help: 'Lessons taught to recent converts where My Covenant Path was intentionally used as part of the lesson.' },

  { type: 'number', title: 'Non-member Texts Sent',
    help: 'The number of text messages sent to non-members today, whether they responded or not. Count every text sent regardless of whether a reply was received.' },

  { type: 'number', title: 'Phone Calls to Non-Members',
    help: 'The number of phone calls you made to non-members today for missionary purposes. Count every call you placed, whether it was answered, went to voicemail, or was missed.' },

  { type: 'number', title: 'Ward Member Contacts Made',
    help: 'Meaningful interactions with ward members that supported missionary work, such as visits, phone calls, texts, or conversations. Casual greetings in sacrament meeting should not be counted.' },

  { type: 'number', title: 'Lessons with Member Present',
    help: 'The number of lessons today where a non-member and a member were both present. This is not your total lesson count — only the ones where a member also attended.' },

  { type: 'number', title: 'References Asked For',
    help: 'The number of times you intentionally asked a ward member for referrals to friends, family, neighbors, or others who may be interested in learning about the gospel. Count each request, even if no referral was given.' },

  { type: 'number', title: 'Member Referrals Received Today',
    help: 'The number of referrals you received directly from ward members today. Do not count online referrals here — only count referrals that came from a specific member you can identify by name. This is a daily count, not a weekly running total.' },

  { type: 'number', title: 'Book of Mormon Shared',
    help: 'The number of copies of the Book of Mormon you gave to non-members today, whether physical or digital. Count each person who received one.' },

  { type: 'number', title: 'Church Invite Given',
    help: 'The number of non-members you personally invited to attend a Church meeting or Church activity today. Count every invitation, whether it was accepted or declined.' },

  { type: 'number', title: 'Lessons where the Doctrine of Baptism is Taught',
    help: 'The number of lessons today where the doctrine of baptism was intentionally taught and discussed. Count each lesson once, whether baptism was introduced for the first time or reviewed as part of the person’s progress.' },

  { type: 'number', title: 'Baptismal Invitations Extended',
    help: 'The number of people you clearly invited to be baptized today. Count every invitation given, regardless of whether the invitation was accepted, declined, or postponed.' },

  { type: 'number', title: 'Baptismal Calendars Given',
    help: 'The number of baptismal calendars or preparation schedules you gave to individuals preparing for baptism. Count each person who received one.' },

  { type: 'effort', title: 'All, Most or Some effort laid on the altar of sacrifice today?',
    help: 'A personal self-assessment of the effort you gave today. Be honest — this is between you and the Lord. Select All if you gave everything you had with no reservations, Most if you worked hard but held something back, or Some if today was a partial effort. This is not about perfection — it is about honesty.' }
];

// Accumulates the expected {title, help} for every item, in creation order,
// so verifyAndFix_ can repair any writes the Advanced Service dropped.
var gExpected = [];

// ==================================================================
// BUILDER
// ==================================================================
function buildDailyReportForm() {
  gExpected = [];

  var form = FormApp.create('Missionary Daily Report');
  form.setDescription('Nightly missionary report. Pick your zone, then your area, then enter today’s numbers.');
  form.setProgressBar(true);
  form.setAllowResponseEdits(false);
  form.setCollectEmail(false);

  // Section 1: the zone selector (choices + branching set after sections exist).
  var zoneItem = form.addListItem();
  setMeta_(zoneItem, 'What zone are you in?', 'The zone you serve in. Select your zone each time you submit the nightly form.');
  zoneItem.setRequired(true);

  // One section per zone.
  var zoneChoices = [];
  var zoneNames = Object.keys(ZONES);
  for (var i = 0; i < zoneNames.length; i++) {
    var zone = zoneNames[i];

    var pageBreak = form.addPageBreakItem();
    setMeta_(pageBreak, zone, null);

    // Area dropdown for this zone.
    var areaItem = form.addListItem();
    setMeta_(areaItem, 'What is your area?', 'The area you serve in. Select your area each time you submit the nightly form.');
    areaItem.setChoiceValues(ZONES[zone]);
    areaItem.setRequired(true);

    // The full nightly question set.
    addQuestions_(form);

    // Finishing this zone's section submits the form (skip the other zones).
    pageBreak.setGoToPage(FormApp.PageNavigationType.SUBMIT);

    // Route the zone selector into this section.
    zoneChoices.push(zoneItem.createChoice(zone, pageBreak));
  }
  zoneItem.setChoices(zoneChoices);

  // New, dedicated responses spreadsheet (kept off any live sheet).
  var ss = SpreadsheetApp.create('Missionary Daily Report (Responses)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  // Self-healing pass: re-open the form (forces a server flush + true read-back)
  // and re-apply any titles/help the Advanced Service dropped during the build.
  verifyAndFix_(form.getId(), gExpected);

  Logger.log('DONE.');
  Logger.log('Form (edit):   ' + form.getEditUrl());
  Logger.log('Form (live):   ' + form.getPublishedUrl());
  Logger.log('Responses sheet: ' + ss.getUrl());
}

function addQuestions_(form) {
  for (var q = 0; q < QUESTIONS.length; q++) {
    var def = QUESTIONS[q];
    var item;
    switch (def.type) {

      case 'date':
        item = form.addDateItem();
        setMeta_(item, def.title, def.help);
        item.setIncludesYear(true).setRequired(true);
        break;

      case 'yesno':
        item = form.addMultipleChoiceItem();
        setMeta_(item, def.title, def.help);
        item.setChoiceValues(['Yes', 'No']).setRequired(true);
        break;

      case 'effort':
        item = form.addMultipleChoiceItem();
        setMeta_(item, def.title, def.help);
        item.setChoiceValues(['All', 'Most', 'Some']).setRequired(true);
        break;

      case 'yes':
        item = form.addCheckboxItem();
        setMeta_(item, def.title, def.help);
        item.setChoiceValues(['Yes']).setRequired(!!def.required);
        break;

      case 'number':
      default:
        item = form.addTextItem();
        setMeta_(item, def.title, def.help);
        item.setRequired(true);
        var validation = FormApp.createTextValidation()
          .setHelpText('Please enter a number (0 or more).')
          .requireNumberGreaterThanOrEqualTo(0)
          .build();
        item.setValidation(validation);
        break;
    }
  }
}

// Sets title/help on a freshly-created item AND records what it should be
// (in creation order) so verifyAndFix_ can repair drops afterward.
function setMeta_(item, title, help) {
  if (title != null) item.setTitle(title);
  if (help != null) item.setHelpText(help);
  gExpected.push({ title: (title != null ? title : null), help: (help != null ? help : null) });
}

// Re-opens the form by ID (forcing pending writes to flush + a true server
// read), then re-applies any title/help that didn't stick. Repeats until a
// fresh read-back is clean or the round cap is hit. Items come back from
// getItems() in creation order, so they line up with gExpected by index.
function verifyAndFix_(formId, expected) {
  var maxRounds = 20;
  for (var round = 1; round <= maxRounds; round++) {
    var f = FormApp.openById(formId);
    var items = f.getItems();
    if (items.length !== expected.length) {
      Logger.log('Verify WARNING: form has ' + items.length + ' items but expected ' + expected.length + '.');
    }
    var fixes = 0;
    var n = Math.min(items.length, expected.length);
    for (var i = 0; i < n; i++) {
      var it = items[i], exp = expected[i];
      if (exp.title != null && it.getTitle() !== exp.title) { it.setTitle(exp.title); fixes++; }
      if (exp.help != null && it.getHelpText() !== exp.help) { it.setHelpText(exp.help); fixes++; }
    }
    Logger.log('Verify round ' + round + ': applied ' + fixes + ' fix(es).');
    if (fixes === 0) { Logger.log('Verify: all titles/help correct.'); return; }
    Utilities.sleep(800);
  }
  // Final read-back to flush the last round of fixes and report the truth.
  var ff = FormApp.openById(formId).getItems();
  var bad = 0, m = Math.min(ff.length, expected.length);
  for (var j = 0; j < m; j++) {
    var e = expected[j];
    if (e.title != null && ff[j].getTitle() !== e.title) bad++;
    if (e.help != null && ff[j].getHelpText() !== e.help) bad++;
  }
  Logger.log(bad === 0
    ? 'Verify: all titles/help correct after final pass.'
    : ('Verify WARNING: ' + bad + ' field(s) still wrong after ' + maxRounds + ' rounds — just re-run the script.'));
}
