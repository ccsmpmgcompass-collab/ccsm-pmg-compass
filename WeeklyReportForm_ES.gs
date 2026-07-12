/**
 * Informe Semanal Misional — Google Form builder (Spanish version)
 * ------------------------------------------------------------------
 * HOW TO USE
 *   1. Go to https://script.google.com  ->  New project.
 *   2. Delete the sample code, paste THIS ENTIRE FILE in.
 *   3. Run  buildWeeklyReportFormES  (first run: approve the permission prompt).
 *   4. The Execution log prints the form's edit + live URLs and the URL of
 *      the freshly-created linked responses spreadsheet.
 *
 * WHAT IT BUILDS
 *   Same structure as WeeklyReportForm.gs (English), but with Spanish titles
 *   and help text throughout, sourced from "CCSM Form Summary (1).md".
 *   Zone/area names are already Spanish place names, so they are unchanged.
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
// DATA — zones -> areas (same organization data as WeeklyReportForm.gs)
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
// DATA — the intro questions asked before the Real/Meta groups (Spanish).
//   type: 'date' | 'yesno'
// ==================================================================
var INTRO_QUESTIONS = [
  { type: 'date', title: '¿Qué fecha está ingresando?',
    help: 'Ingrese la fecha correspondiente al día que está reportando. En la mayoría de los casos, será la fecha de hoy. Si está registrando información de un día anterior, ingrese la fecha en que realmente ocurrieron las actividades, no la fecha en que está enviando el informe.' },

  { type: 'yesno', title: '¿Recibió una llamada de sus líderes?',
    help: 'Seleccione Sí si recibió una llamada de ministración de sus líderes durante esta semana. Seleccione No si no recibió una llamada de ministración durante esta semana.' },

  { type: 'yesno', title: '¿Usted y sus líderes locales realizaron una reunión de coordinación semanal?',
    help: 'Seleccione Sí si participó en una reunión de coordinación semanal con los líderes de su barrio o rama. Seleccione No si no se llevó a cabo una reunión de coordinación semanal durante la semana.' }
];

// ==================================================================
// DATA — the 7 weekly key indicators, in order (Spanish). Rendered twice:
// once as "Real" results, once as "Meta" targets — matches the source doc.
// ==================================================================
var KEY_INDICATORS = [
  'Nuevas personas encontradas',
  'Lecciones con miembros',
  'Amigos en la reunión sacramental',
  'Amigos en la Iglesia durante su primera semana de enseñanza',
  'Amigos con fecha bautismal',
  'Bautizados y confirmados',
  'Conversos recientes en la Iglesia'
];

// Accumulates the expected {title, help} for every item, in creation order,
// so verifyAndFix_ can repair any writes the Advanced Service dropped.
var gExpected = [];

// ==================================================================
// BUILDER
// ==================================================================
function buildWeeklyReportFormES() {
  gExpected = [];

  var form = FormApp.create('Informe Semanal Misional');
  form.setDescription('Informe misional semanal. Elija su zona, luego su área, y luego ingrese los resultados de esta semana y las metas de la próxima semana.');
  form.setProgressBar(true);
  form.setAllowResponseEdits(false);
  form.setCollectEmail(false);

  // Section 1: the zone selector (choices + branching set after sections exist).
  var zoneItem = form.addListItem();
  setMeta_(zoneItem, '¿En qué zona sirve?', 'La zona en la que usted sirve. Seleccione su zona cada vez que envíe el informe semanal.');
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
    setMeta_(areaItem, '¿En qué área sirve?', 'El área en la que usted sirve. Seleccione su área cada vez que envíe el informe semanal.');
    areaItem.setChoiceValues(ZONES[zone]);
    areaItem.setRequired(true);

    addIntroQuestions_(form);
    addKeyIndicatorGroup_(form, 'Indicadores Clave Semanales (Resultados)',
      'Estos indicadores representan los resultados obtenidos durante la semana pasada, de acuerdo con las normas establecidas en Predicad Mi Evangelio. Ingrese los mismos números que registró en los indicadores clave semanales de la aplicación Predicad Mi Evangelio.',
      KEY_INDICATORS, 'Real');
    addKeyIndicatorGroup_(form, 'Indicadores Clave Semanales (Metas)',
      'Estos indicadores representan las metas que usted estableció durante la planificación semanal para la semana siguiente, de acuerdo con las normas establecidas en Predicad Mi Evangelio. Ingrese las mismas metas que registró en la aplicación Predicad Mi Evangelio.',
      KEY_INDICATORS, 'Meta');

    // Finishing this zone's section submits the form (skip the other zones).
    pageBreak.setGoToPage(FormApp.PageNavigationType.SUBMIT);

    // Route the zone selector into this section.
    zoneChoices.push(zoneItem.createChoice(zone, pageBreak));
  }
  zoneItem.setChoices(zoneChoices);

  // New, dedicated responses spreadsheet (kept off any live sheet).
  var ss = SpreadsheetApp.create('Informe Semanal Misional (Respuestas)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  // Self-healing pass: re-open the form (forces a server flush + true read-back)
  // and re-apply any titles/help the Advanced Service dropped during the build.
  verifyAndFix_(form.getId(), gExpected);

  Logger.log('DONE.');
  Logger.log('Form (edit):   ' + form.getEditUrl());
  Logger.log('Form (live):   ' + form.getPublishedUrl());
  Logger.log('Responses sheet: ' + ss.getUrl());
}

function addIntroQuestions_(form) {
  for (var q = 0; q < INTRO_QUESTIONS.length; q++) {
    var def = INTRO_QUESTIONS[q];
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
        item.setChoiceValues(['Sí', 'No']).setRequired(true);
        break;
    }
  }
}

function addKeyIndicatorGroup_(form, sectionTitle, sectionHelp, titles, suffix) {
  var header = form.addSectionHeaderItem();
  setMeta_(header, sectionTitle, sectionHelp);

  for (var k = 0; k < titles.length; k++) {
    var item = form.addTextItem();
    setMeta_(item, titles[k] + ' (' + suffix + ')', null);
    item.setRequired(true);
    var validation = FormApp.createTextValidation()
      .setHelpText('Ingrese un número (0 o más).')
      .requireNumberGreaterThanOrEqualTo(0)
      .build();
    item.setValidation(validation);
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
