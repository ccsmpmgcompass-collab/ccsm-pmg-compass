/**
 * Informe Diario Misional — Google Form builder (Spanish version)
 * ------------------------------------------------------------------
 * HOW TO USE
 *   1. Go to https://script.google.com  ->  New project.
 *   2. Delete the sample code, paste THIS ENTIRE FILE in.
 *   3. Run  buildDailyReportFormES  (first run: approve the permission prompt).
 *   4. The Execution log prints the form's edit + live URLs and the URL of
 *      the freshly-created linked responses spreadsheet.
 *
 * WHAT IT BUILDS
 *   Same structure as DailyReportForm.gs (English), but with Spanish titles
 *   and help text throughout, sourced from "CCSM Form Summary (2).md".
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
// DATA — zones -> areas (same organization data as DailyReportForm.gs)
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
// DATA — the per-area question set, in order (Spanish).
//   type: 'date' | 'yesno' | 'number' | 'effort' | 'yes'
//   yes  = single "Sí" checkbox (required flag set per item)
// ==================================================================
var QUESTIONS = [
  { type: 'date',   title: '¿Qué fecha está ingresando?',
    help: 'Ingrese la fecha correspondiente al día que está reportando. En la mayoría de los casos, será la fecha de hoy. Si está registrando información de un día anterior, ingrese la fecha en que realmente ocurrieron las actividades, no la fecha en que está enviando el informe.' },

  { type: 'yesno',  title: '¿Participó en uno o más intercambios?',
    help: 'Seleccione Sí si participó en un intercambio aprobado durante el día. Seleccione No si permaneció con su compañerismo habitual durante todo el día.' },

  { type: 'number', title: 'Prácticas de enseñanza realizadas hoy',
    help: 'Ingrese la cantidad de prácticas de enseñanza que realizó hoy para practicar cómo enseñar, encontrar personas o extender invitaciones. Cuente cada práctica por separado, ya sea realizada con su compañero(a), sus líderes u otros misioneros.' },

  { type: 'number', title: 'Intentos de contacto con amigos',
    help: 'Cuente cada intento de contactar a un amigo hoy, independientemente de si la persona respondió o no. Si nadie respondió, igualmente cuenta aquí. Esto también incluye los intentos realizados en lugares públicos; no es necesario que el contacto haya sido en una puerta.' },

  { type: 'number', title: 'Contactos con amigos',
    help: 'Cuente cada ocasión en la que una persona respondió y usted logró establecer contacto. Todo contacto también cuenta como un intento de contacto. Esto también incluye los contactos realizados en lugares públicos; no es necesario que hayan ocurrido en una puerta.' },

  { type: 'number', title: 'Conversaciones significativas con amigos',
    help: 'Una conversación con un amigo que duró más de tres minutos e incluyó un principio o mensaje del evangelio. Sea honesto consigo mismo: ¿fue realmente una conversación significativa? Si la respuesta es sí, también cuenta como un contacto y un intento de contacto.' },

  { type: 'number', title: 'Nuevas personas encontradas',
    help: 'Cada persona (que no haya sido bautizada) que haya recibido una lección durante la semana, que no haya sido enseñada en los últimos tres meses y que haya aceptado una cita específica para regresar. Normalmente, una lección incluye una oración (cuando sea apropiado), la enseñanza de al menos un principio del evangelio y una invitación.' },

  { type: 'number', title: 'Lecciones con amigos',
    help: 'Una visita con un amigo en la que usted enseñó un principio del evangelio y extendió una invitación. Cada lección también cuenta como una conversación significativa, un contacto y un intento de contacto. El número de lecciones nunca debe ser mayor que el de conversaciones significativas. Si lo es, revise nuevamente sus registros.' },

  { type: 'number', title: 'Lecciones con familias en las que no todos son miembros',
    help: 'Una lección dada en un hogar donde algunos miembros de la familia pertenecen a la Iglesia y otros no. Cuente cada lección como una sola, aunque hayan participado varios miembros de la familia.' },

  { type: 'number', title: 'Lecciones con conversos recientes',
    help: 'Las lecciones dadas hoy únicamente a conversos recientes. No incluya amigos en este conteo; es exclusivamente para conversos recientes.' },

  { type: 'number', title: 'Lecciones con conversos recientes usando Mi Senda de los Convenios',
    help: 'Lecciones impartidas a conversos recientes en las que se utilizó intencionalmente Mi Senda de los Convenios como parte de la enseñanza.' },

  { type: 'number', title: 'Mensajes de texto enviados a amigos',
    help: 'La cantidad de mensajes de texto enviados hoy a amigos, hayan respondido o no. Cuente cada mensaje enviado, independientemente de si recibió una respuesta.' },

  { type: 'number', title: 'Llamadas telefónicas a amigos',
    help: 'El número de llamadas que realizó hoy a amigos con fines misionales. Cuente todas las llamadas realizadas, ya hayan sido contestadas, enviadas al buzón de voz o no contestadas.' },

  { type: 'number', title: 'Contactos realizados con miembros del barrio',
    help: 'Interacciones significativas con miembros del barrio que apoyaron la obra misional, como visitas, llamadas telefónicas, mensajes de texto o conversaciones. No cuente saludos casuales durante la reunión sacramental.' },

  { type: 'number', title: 'Lecciones con un miembro presente',
    help: 'La cantidad de lecciones dadas hoy en las que estuvieron presentes tanto un amigo como un miembro de la Iglesia. No corresponde al total de lecciones, sino únicamente a aquellas en las que también participó un miembro.' },

  { type: 'number', title: 'Referencias solicitadas',
    help: 'La cantidad de veces que usted pidió intencionalmente a un miembro del barrio referencias de amigos, familiares, vecinos u otras personas que pudieran estar interesadas en aprender acerca del evangelio. Cuente cada solicitud, aunque no haya recibido ninguna referencia.' },

  { type: 'number', title: 'Referencias de miembros recibidas hoy',
    help: 'La cantidad de referencias que recibió hoy directamente de miembros del barrio. No incluya referencias recibidas por Internet; cuente únicamente aquellas proporcionadas por un miembro específico que pueda identificar por nombre. Este es un conteo diario, no un total acumulado de la semana.' },

  { type: 'number', title: 'Copias del Libro de Mormón entregadas',
    help: 'La cantidad de copias del Libro de Mormón que entregó hoy a amigos, ya sean físicos o digitales. Cuente cada persona que recibió uno.' },

  { type: 'number', title: 'Invitaciones a la Iglesia extendidas',
    help: 'La cantidad de amigos a quienes usted invitó personalmente a asistir a una reunión o actividad de la Iglesia hoy. Cuente cada invitación, independientemente de si fue aceptada o rechazada.' },

  { type: 'number', title: 'Lecciones en las que se enseñó la doctrina del bautismo',
    help: 'La cantidad de lecciones impartidas hoy en las que se enseñó y analizó intencionalmente la doctrina del bautismo. Cuente cada lección una sola vez, ya sea que el bautismo se haya presentado por primera vez o se haya repasado como parte del progreso de la persona.' },

  { type: 'number', title: 'Invitaciones al bautismo extendidas',
    help: 'La cantidad de personas a quienes invitó claramente a bautizarse hoy. Cuente cada invitación, independientemente de si fue aceptada, rechazada o pospuesta.' },

  { type: 'number', title: 'Calendarios bautismales entregados',
    help: 'La cantidad de calendarios bautismales o planes de preparación para el bautismo que entregó a personas que se están preparando para bautizarse. Cuente cada persona que recibió uno.' },

  { type: 'effort', title: '¿Dio todo, la mayor parte o algo de esfuerzo en el altar del sacrificio hoy?',
    help: 'Una autoevaluación personal del esfuerzo que usted dio hoy. Sea honesto: esto es entre usted y el Señor. Seleccione Todo si dio todo lo que tenía sin reservas, La mayor parte si trabajó diligentemente pero sintió que pudo haber dado un poco más, o Algo si su esfuerzo fue solo parcial. No se trata de ser perfecto, sino de ser honesto.' }
];

// Accumulates the expected {title, help} for every item, in creation order,
// so verifyAndFix_ can repair any writes the Advanced Service dropped.
var gExpected = [];

// ==================================================================
// BUILDER
// ==================================================================
function buildDailyReportFormES() {
  gExpected = [];

  var form = FormApp.create('Informe Diario Misional');
  form.setDescription('Informe misional nocturno. Elija su zona, luego su área, y luego ingrese los números de hoy.');
  form.setProgressBar(true);
  form.setAllowResponseEdits(false);
  form.setCollectEmail(false);

  // Section 1: the zone selector (choices + branching set after sections exist).
  var zoneItem = form.addListItem();
  setMeta_(zoneItem, '¿En qué zona sirve?', 'La zona en la que usted sirve. Seleccione su zona cada vez que envíe el informe nocturno.');
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
    setMeta_(areaItem, '¿En qué área sirve?', 'El área en la que usted sirve. Seleccione su área cada vez que envíe el informe nocturno.');
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
  var ss = SpreadsheetApp.create('Informe Diario Misional (Respuestas)');
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
        item.setChoiceValues(['Sí', 'No']).setRequired(true);
        break;

      case 'effort':
        item = form.addMultipleChoiceItem();
        setMeta_(item, def.title, def.help);
        item.setChoiceValues(['Todo', 'La mayor parte', 'Algo']).setRequired(true);
        break;

      case 'yes':
        item = form.addCheckboxItem();
        setMeta_(item, def.title, def.help);
        item.setChoiceValues(['Sí']).setRequired(!!def.required);
        break;

      case 'number':
      default:
        item = form.addTextItem();
        setMeta_(item, def.title, def.help);
        item.setRequired(true);
        var validation = FormApp.createTextValidation()
          .setHelpText('Ingrese un número (0 o más).')
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
