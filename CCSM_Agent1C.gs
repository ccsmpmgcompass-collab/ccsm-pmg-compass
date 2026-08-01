/**
 * ============================================================
 * CCSM_Agent1C.gs — Sunday Coaching: Email Sender
 * PMG Compass | Chile Concepción South Mission (CCSM) — Spanish fork
 * ============================================================
 *
 * Fork of Agent1C.gs (docs/Agent1C.gs in PMG-Compass) for the CCSM Spanish
 * form set — the final link in the Sunday coaching chain (Agent1A → Agent1B
 * → Agent1C). All email structural text is Spanish (exact translations per
 * task-8 brief). Personal area coaching stays entirely pre-written
 * (MESSAGE_BANK, via Agent1B) — nothing AI-generated is ever sent to a
 * missionary. Leadership narratives ARE Gemini-generated (allowed — see
 * CCSM_Helpers.gs HARD RULE comment) and are sent to trained leaders only.
 *
 * CCSM-SPECIFIC ADAPTATIONS FROM PROVO'S Agent1C.gs:
 *
 * 1. DROPPED WEEKLY-KI FIELDS — Provo's Agent1C reads pew/date_metric/gate/
 *    renew (Provo's weekly-KI parse) throughout its KPI tiles, area data
 *    table, area detail panel, WEEKLY_BREAKDOWNS header, and Gemini prompts.
 *    CCSM_Agent1A.gs's own header comment documents that this weekly-KI
 *    parser has NO CCSM equivalent and was dropped entirely (CCSM_Agent1A.gs
 *    a1a_buildStats only sees DAILY_LOG aggregates + the 5 CCSM rate
 *    metrics). Every one of those sections below is rewritten against
 *    CCSM's actual metric set: the 5 rate metrics in A1A_RATE_METRICS
 *    (CCSM_Agent1A.gs) — contact_rate, mc_rate, lesson_rate, close_rate,
 *    effort_score — plus the dynamic NIGHTLY NUMBER metrics from
 *    QUESTIONS_CONFIG (contacts_made, meaningful_conversations,
 *    new_people_found, friend_lessons, baptismal_invitations, etc.). No
 *    English/Provo-only field name (pew, date_metric, gate, renew, nm_*,
 *    door*) appears anywhere in this file.
 *
 * 2. MESSAGE_BANK field access — CCSM_Helpers.gs's getMessageBank() (used by
 *    Agent1B's a1b_pickAndAttach) returns camelCase fields (messageId,
 *    subjectLine, bodyText, pmgPage, pmgDescription, scripture,
 *    scriptureText) — NOT Provo's bracket-string keys ('Subject_Line',
 *    'Body_Text', ...). Every message-rendering function here reads the
 *    camelCase shape.
 *
 * 3. LEADERSHIP ROLES LIVE ON REAL AREA ROWS — Provo's MISSION_ORG has
 *    dedicated leadership-only tracking rows (Zone='ALL', or Area_Name like
 *    "Zone Leader - X") separate from a person's real teaching area; a
 *    companionship's calling flag (Is_ZL etc.) on their OWN area row is
 *    legitimately true without making that row leadership-only. CCSM's
 *    actual roster (CcsmData.gs CCSM_MISSION_ORG_ROWS) has NO separate
 *    tracking rows at all — Is_DL/Is_ZL/Is_STL/Is_AP/Is_MP are flags
 *    directly on a companionship's own real area (e.g. Arauco 1 / A014 is a
 *    Zone Leader's own area). a1c_buildPeopleMap() below adds BOTH the
 *    area AND the role for such a row (Provo's version was either/or,
 *    gated on a1c_isLeadershipRow which never fires on real CCSM data) —
 *    see the comment inside a1c_buildPeopleMap for detail.
 *
 * 4. FEEDBACK_HISTORY — reuses CCSM_Helpers.gs's shared recordMessageSent()
 *    (already keyed exactly to FEEDBACK_HISTORY's real schema — see
 *    CcsmData.gs CCSM_TAB_SPECS note) instead of Provo's inline sheet
 *    surgery. Task 8 owns this call (Agent1B intentionally defers it — see
 *    CCSM_Agent1B.gs file header). recordMessageSent() gained an optional
 *    4th `growthMetric` argument (CCSM_Helpers.gs) so Agent1C can still set
 *    Last_Growth_Metric, matching Provo's a1c_writeFeedbackHistory behavior,
 *    without duplicating the upsert logic. Only msg_strength1's ID is
 *    recorded under SUNDAY_COACHING_STRENGTH (mirrors Provo's original
 *    choice — FEEDBACK_HISTORY has one row per area+category, so recording
 *    both strength1 and strength2 would just overwrite one with the other).
 *
 * 5. WEEKLY_BREAKDOWNS — header/columns are derived at write time from
 *    QUESTIONS_CONFIG's active NIGHTLY NUMBER metrics (a1c_loadCountMetricKeys,
 *    mirrors CCSM_Agent1A.gs's own a1a_loadCountMetrics) plus the 5 fixed
 *    CCSM rate-metric keys — never Provo's fixed English column list.
 *
 * 6. Dates — every timezone use goes through getMissionTimezone(). Spanish
 *    month names use a fixed 12-entry array (A1C_SPANISH_MONTHS) rather than
 *    trusting Utilities.formatDate's 'MMMM' token to localize (it doesn't —
 *    GAS/Java's default locale renders English month names regardless of
 *    script locale; confirmed against this project's own gas_stubs.js,
 *    which only defines English MONTH_NAMES).
 *
 * WHAT IT DOES:
 * 1. Loads enriched area data (stats + selected messages) from Script
 *    Properties (A1B_DATA)
 * 2. Loads MISSION_ORG to build a per-person map (email → areas + roles)
 * 3. Sends ONE combined HTML email per unique email address
 * 4. ALL emails route through Relay 2 (agentName = 'Agent1C', see
 *    CCSM_Helpers.gs sendEmail())
 * 5. Writes one row per area to WEEKLY_BREAKDOWNS
 * 6. Records sent messages in FEEDBACK_HISTORY via recordMessageSent()
 * 7. Cleans up Script Properties (A1A_DATA and A1B_DATA)
 * 8. Logs to AGENT_RUN_LOG
 */

// ─── MODULE STATE ──────────────────────────────────────────────────────────────
// Narrative cache keyed by 'scope:unitName' — lives only for the current execution.
// Populated by a1c_pregenerateNarratives() at run start; used by a1c_buildLeadershipNarrative().
var _narrativeCache = {};

// Spanish month names — see file header note #6. Index 0 = enero.
var A1C_SPANISH_MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

// The 5 rate metrics computed by CCSM_Agent1A.gs (A1A_RATE_METRICS) — fixed,
// mission-wide, always present on every area's stats regardless of whether
// the area submitted this week (a1a_buildStats always sets all 5).
var A1C_RATE_METRIC_KEYS = ['contact_rate', 'mc_rate', 'lesson_rate', 'close_rate', 'effort_score'];

// Curated metric subset shown in KPI tiles / the area data table (concise,
// human-scannable — mirrors Provo's own curated-subset design; the FULL
// metric set appears in the per-area detail panel, see
// a1c_buildAreaDetailPanel_).
var A1C_TABLE_METRICS = [
  { key: 'contacts_made',            label: 'Contactos' },
  { key: 'meaningful_conversations', label: 'Signif.' },
  { key: 'new_people_found',         label: 'Nuevas' },
  { key: 'friend_lessons',           label: 'Lecciones' },
  { key: 'baptismal_invitations',    label: 'Inv. Baut.' }
];

// ─── PERSONAL-SECTION NUMBERS (Stage 2, 2026-08-01) ─────────────────────────
// The area coaching section used to be documented "intentionally
// NUMBER-FREE" (see the old a1c_buildAreaSection comment this replaced).
// Same reversal Provo's own coaching letter went through — see
// [[project-coaching-letter-accuracy-stats]]: "Personal sections show
// numbers again... ONLY the area's own numbers, OK to span transfers,
// NEVER the 4 AgentScores scores, no area-vs-area/mission averages." CCSM's
// phase-5 mandate ("raise detail to Provo's level") is that same decision
// for this mission.

// Only these 4 are true 0-1 fractions (displayed as a percent). effort_score
// is deliberately NOT here: unlike whatever scale Provo's own effort_score
// used, CCSM_Agent1A.gs's a1a_buildStats computes it as a straight 1-3
// weighted average (Todo=3 / La mayor parte=2 / Algo=1), never a fraction —
// so it is formatted (and delta'd) as a plain one-decimal number, not
// multiplied by 100.
var A1C_PERCENT_METRIC_KEYS = ['contact_rate', 'mc_rate', 'lesson_rate', 'close_rate'];

function a1c_fmtMetricVal_(key, val) {
  if (val === null || val === undefined || typeof val !== 'number' || isNaN(val)) return '—';
  if (A1C_PERCENT_METRIC_KEYS.indexOf(key) !== -1) return Math.round(val * 100) + '%';
  if (key === 'effort_score') return String(a1a_round1(val));
  return String(Math.round(val));
}

// Spanish display labels for every CCSM metric the scoreboard/goal grid can
// show — the 5 rate metrics plus every real QUESTIONS_CONFIG nightly metric
// (see [[project-ccsm-readiness-aug7]]'s catalogue). Falls back to the raw
// key if a future QUESTIONS_CONFIG addition isn't listed here yet (never a
// blank label — see a1c_scoreboardLabel_).
var A1C_METRIC_LABELS = {
  contact_rate: 'Tasa de Contacto', mc_rate: 'Tasa de Significativas',
  lesson_rate: 'Tasa de Lecciones', close_rate: 'Tasa de Compromiso',
  effort_score: 'Esfuerzo',
  contacts_attempted: 'Contactos Intentados', contacts_made: 'Contactos Logrados',
  meaningful_conversations: 'Conversaciones Significativas', new_people_found: 'Nuevas Personas',
  friend_texts: 'Mensajes de Texto', friend_calls: 'Llamadas',
  friend_lessons: 'Lecciones a Amigos', pmf_lessons: 'Lecciones PMF',
  rc_lessons: 'Lecciones a Conversos Recientes', rc_lessons_mcp: 'Lecciones CR con Miembro',
  lessons_member_present: 'Lecciones con Miembro Presente', member_contacts: 'Contactos de Miembros',
  references_asked: 'Referencias Pedidas', member_referrals_received: 'Referencias de Miembros',
  bom_shared: 'Libros de Mormón Compartidos', roleplays: 'Juegos de Rol',
  church_invites: 'Invitaciones a la Iglesia', baptism_doctrine_lessons: 'Lecciones de Doctrina Bautismal',
  baptismal_invitations: 'Invitaciones al Bautismo', baptismal_calendars: 'Calendarios de Bautismo'
};

function a1c_scoreboardLabel_(key) {
  return A1C_METRIC_LABELS[key] || key;
}

// Scoreboard groups follow the same Buscar/Ensenar/Invitar funnel language
// already used by this file's _LEADERSHIP_MSGS themes. Named metrics first;
// any OTHER numeric nightly metric the mission tracks (dynamic via
// QUESTIONS_CONFIG/DAILY_LOG, e.g. a newly added question) lands in
// 'Otros' rather than being silently dropped.
var A1C_SCOREBOARD_GROUPS = [
  { title: '🚪 BUSCAR — Formulario Nocturno',
    keys: ['contacts_attempted', 'contacts_made', 'contact_rate', 'meaningful_conversations',
           'mc_rate', 'new_people_found', 'friend_texts', 'friend_calls'] },
  { title: '📚 ENSEÑAR — Formulario Nocturno',
    keys: ['friend_lessons', 'lesson_rate', 'pmf_lessons', 'rc_lessons', 'rc_lessons_mcp',
           'lessons_member_present', 'member_contacts', 'references_asked',
           'member_referrals_received', 'bom_shared', 'roleplays'] },
  { title: '⛪ INVITAR — Formulario Nocturno',
    keys: ['church_invites', 'baptism_doctrine_lessons', 'baptismal_invitations',
           'baptismal_calendars', 'close_rate'] }
];

function a1c_shortDate_(weekEnd) {
  var m = String(weekEnd || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return '';
  return parseInt(m[3], 10) + ' ' + A1C_SPANISH_MONTHS[parseInt(m[2], 10) - 1].substr(0, 3);
}

/** Title + ' · 12 ago' salt (empty salt -> title unchanged). Salting makes
 *  each week's repeated section titles read as NEW content to Gmail, so its
 *  '⋯' trim has less to hide. */
function a1c_saltTitle_(title, weekEnd) {
  var d = a1c_shortDate_(weekEnd);
  return d ? title + ' · ' + d : title;
}

// Leadership coaching message bank — human-curated, never AI-generated. One
// is picked (theme matched to the zone/district's actual growth-focus data)
// and appended to each zone/district leadership email after the data table.
// Always "amigos" — never "investigador".
var _LEADERSHIP_MSGS = [
  // ── BUSCAR (Finding) ────────────────────────────────────────────────────────
  {
    theme:    'Buscar',
    subject:  'Cada Contacto Es una Conversación en Potencia',
    body:     'Los números muestran cuántos contactos se intentaron — pero la pregunta que vale la pena hacer es qué pasó después. Esta semana en el inventario de compañerismo, anime a sus líderes de distrito a averiguar: de cada contacto realizado, ¿cuántos se convirtieron en una conversación real, y cuántos en una cita de regreso confirmada? Una conversación genuina con una próxima visita concreta es la unidad de trabajo que mueve a las personas hacia el bautismo.',
    pmg:      '157',
    scripture:'D. y C. 4:4-5',
    scriptText:'Por tanto, oh vosotros que os embarcáis al servicio de Dios, ved que le sirváis con todo vuestro corazón, alma, mente y fuerza.'
  },
  {
    theme:    'Buscar',
    subject:  'Las Referencias Necesitan una Respuesta el Mismo Día',
    body:     'Cada referencia que recibe su zona tiene una ventana de oportunidad. Cuando un miembro entrega el nombre de un amigo, un intento de contacto el mismo día no es solo una buena práctica — es una declaración a ese miembro de que se toma en serio su confianza. Revise esta semana: ¿recibió cada referencia un intento de contacto dentro de 24 horas? Conviértalo en un estándar de zona y reconozca a los misioneros que lo hacen sin que se les recuerde.',
    pmg:      '164',
    scripture:'D. y C. 88:81',
    scriptText:'He aquí, os envié a testificar y amonestar al pueblo, y le corresponde a todo hombre que ha sido amonestado amonestar a su prójimo.'
  },
  // ── ENSEÑAR (Teaching) ──────────────────────────────────────────────────────
  {
    theme:    'Enseñar',
    subject:  'Una Lección Más Cambia la Trayectoria',
    body:     'Los amigos que reciben más de una lección por semana progresan a un ritmo notablemente más rápido. Mire los números de enseñanza de su zona y pregunte a sus líderes de distrito: ¿a qué amigos se les está viendo dos veces por semana, y cuáles llevan diez días sin una lección? Anime a sus misioneros a planificar dos visitas por amigo como norma, no como excepción.',
    pmg:      '174',
    scripture:'Alma 26:22',
    scriptText:'Sí, aquel que se arrepiente y ejerce la fe, y produce buenas obras, y ora continuamente sin cesar — a tal se le concede conocer los misterios de Dios.'
  },
  {
    theme:    'Enseñar',
    subject:  'Las Lecciones con Miembro Presente Son el Estándar',
    body:     'Un amigo que llega al bautismo sin haber estado nunca en una sala con un miembro del barrio es un amigo en riesgo. Esta semana, pida a cada compañerismo que identifique un miembro que llevarán a una lección antes del domingo — no necesita ser alguien del consejo de barrio, solo una persona amigable de la Iglesia que pueda sentarse con un nuevo amigo.',
    pmg:      '85',
    scripture:'D. y C. 11:21',
    scriptText:'Escudriña las Escrituras; procura obtener sabiduría; asocíate con lo bueno, con lo que edifica.'
  },
  // ── INDICADORES CLAVE (Key Indicators) ──────────────────────────────────────
  {
    theme:    'Indicadores Clave',
    subject:  'Una Fecha Bautismal Es una Promesa, No una Fecha Límite',
    body:     'Fijar una fecha no es presión — es el regalo de una meta. Cuando un amigo se compromete con una fecha bautismal, cada cita posterior, cada visita a la reunión sacramental, cada presentación con un miembro cobra más sentido. Mire las invitaciones al bautismo de su zona y pregunte a sus líderes: ¿cómo se extendieron esas invitaciones? ¿Fueron pedidas con fe, ligadas al testimonio que el amigo ya está desarrollando?',
    pmg:      '205',
    scripture:'Moroni 10:4',
    scriptText:'Y cuando recibáis estas cosas, quisiera exhortaros a que preguntaseis a Dios, el Padre Eterno, en el nombre de Cristo, si no son verdaderas estas cosas.'
  },
  {
    theme:    'Indicadores Clave',
    subject:  'Pida un Compromiso Cada Vez',
    body:     'Toda lección debería terminar con un compromiso claro y específico — no una invitación vaga a pensarlo, sino una petición real con una respuesta. Practique en su próxima reunión de zona o distrito: ¿pueden sus misioneros pedir una fecha bautismal con naturalidad, sin dudar, sin disculparse por la pregunta? Un misionero que no pregunta priva a sus amigos de la oportunidad de decir que sí.',
    pmg:      '205',
    scripture:'2 Nefi 31:17',
    scriptText:'Por tanto, haced las cosas que os he dicho que he visto que haría vuestro Señor y vuestro Redentor.'
  },
  // ── CULTURA DE ZONA (Zone Culture) ──────────────────────────────────────────
  {
    theme:    'Cultura de Zona',
    subject:  'El Informe Nocturno Es Rendir Cuentas al Señor',
    body:     'La constancia en el informe refleja la cultura de la zona. Cuando los misioneros informan cada noche, rinden cuentas al Señor, a usted y entre ellos — no solo llenan un formulario. Revise el patrón de informes de esta semana y aborde con amor cualquier área inconstante, ayudando a los misioneros a entender que un informe nocturno honesto es parte de su convenio de servir con integridad.',
    pmg:      null,
    scripture:'D. y C. 59:21',
    scriptText:'Y en nada ofende el hombre a Dios, ni se enciende su ira, sino contra aquellos que no confiesan su mano en todas las cosas, ni obedecen sus mandamientos.'
  },
  {
    theme:    'Cultura de Zona',
    subject:  'Reconozca a Sus Misioneros por lo que Hacen Bien',
    body:     'Esta semana, encuentre algo específico que cada compañerismo de su zona está haciendo bien — y dígalo en voz alta. No un ánimo genérico, sino un reconocimiento concreto: "Contactaron esa referencia el mismo día que llegó. Ese es el estándar." Los misioneros que se sienten genuinamente vistos por sus líderes trabajan con más ánimo y se mantienen espiritualmente más fuertes.',
    pmg:      null,
    scripture:'D. y C. 121:41',
    scriptText:'Ningún poder o influencia puede o debe mantenerse en virtud del sacerdocio, sino por medio de la persuasión, de la longanimidad, de la benignidad y la mansedumbre, y del amor sincero.'
  },
  // ── FE (Faith) ───────────────────────────────────────────────────────────────
  {
    theme:    'Fe',
    subject:  'Su Zona Sigue Su Fe',
    body:     'El tono espiritual de su zona lo marca usted. Cuando testifica con sencillez, cuando habla de sus amigos con amor genuino en lugar de tratarlos como un número, cuando modela lo que significa trabajar con esfuerzo y confiar en Dios con los resultados — sus misioneros lo absorben y lo llevan a sus áreas. Esta semana, pregúntese con honestidad: ¿qué cree posible mi zona? Luego enséñeles a creer un poco más.',
    pmg:      null,
    scripture:'Alma 26:12',
    scriptText:'Sé que no soy nada; en cuanto a mi propia fuerza, soy débil; por tanto, no me jactaré de mí mismo, sino que me jactaré de mi Dios, porque en su fuerza puedo hacer todas las cosas.'
  },
  {
    theme:    'Fe',
    subject:  'La Obra Es de Él',
    body:     'Cada amigo que se enseña en su zona es un hijo de Dios que el Señor ha estado preparando desde mucho antes de que sus misioneros tocaran su puerta. Su labor no es fabricar la conversión — es presentarse, enseñar con el Espíritu, extender invitaciones con fe, y dejar el resultado en manos de Él. Si los números de esta semana no son los que esperaba, llévelo al Señor en oración y pregunte qué ve Él que usted no ve.',
    pmg:      null,
    scripture:'D. y C. 18:15',
    scriptText:'Y si sucede que trabajáis todos vuestros días clamando arrepentimiento a este pueblo, y me traéis, aunque sea una sola alma, ¡cuán grande será vuestro gozo!'
  }
];

// ─── MAIN ENTRY POINT ──────────────────────────────────────────────────────────
function runAgent1C() {
  var status = 'SUCCESS';
  var notes = [];
  try {
    Logger.log('Agent1C: Starting email send — ' + new Date().toISOString());

    // Load Agent1B's enriched output. loadTempData() already parses the JSON
    // it stored (see CCSM_Helpers.gs) — payload IS the object saveTempData
    // saved, not a raw string (unlike Provo's Helpers.gs loadTempData).
    var payload = loadTempData('A1B_DATA');
    if (!payload) throw new Error('A1B_DATA not found in Script Properties. Did Agent1B run?');

    var weekEnd   = payload.weekEnd   || '';
    var weekStart = payload.weekStart || '';
    var areas     = payload.areas     || {};
    var summaries = payload.summaries || {};

    // Pre-generate all zone + district narratives in 2 batch Gemini calls —
    // collapses N per-unit calls into 2 total (mission narrative, if needed,
    // is generated on demand and cached). See a1c_pregenerateNarratives.
    a1c_pregenerateNarratives(summaries, areas, weekEnd);

    // Build people map: email → { name, areas[], roles[] }
    var fullOrgData = a1c_loadFullMissionOrg();
    var peopleMap   = a1c_buildPeopleMap(fullOrgData);

    var emailsSent  = 0;
    var emailErrors = 0;
    var quotaSkipped = 0;

    // ── Quota guard ────────────────────────────────────────────────────────
    // This loop is the single largest mail burst in the whole system: one
    // email per unique address in MISSION_ORG, measured at 97 on the live
    // roster (45 with leaders only). A consumer @gmail.com account gets 100
    // MailApp recipients/day, shared with Agent3's missed-day alerts, Agent6
    // and AgentEscalation.
    //
    // Without a guard the failure is silent and expensive: MailApp throws
    // "Service invoked too many times for one day: email" partway through,
    // every remaining missionary is skipped, the per-email catch below just
    // increments emailErrors, and the run is still logged SUCCESS. That
    // already happened on the live sheet -- Agent3 sent 97 alerts on
    // 2026-07-29 and its every run since has logged the same quota error
    // under a SUCCESS status.
    //
    // ac1_relayConfigured() mirrors sendEmail()'s own routing check: when
    // RELAY_2_URL is set, Agent1C's mail leaves through the relay account's
    // UrlFetchApp quota and never touches this account's MailApp allowance,
    // so the guard must not fire. Same pattern as
    // CCSM_AgentEscalation.ae_relayConfigured().
    var usingRelay = a1c_relayConfigured();

    Object.keys(peopleMap).forEach(function(email) {
      if (!email || email.indexOf('@') < 0) return;
      if (email.toLowerCase().indexOf('notreadyyet') >= 0) return;
      if (email.toLowerCase().indexOf('tbd@') >= 0) return;

      // Checked per-iteration, not once up front: the quota is consumed BY
      // this loop, so a single check before it would pass and then blow
      // through the limit anyway.
      if (!usingRelay && MailApp.getRemainingDailyQuota() < 1) {
        quotaSkipped++;
        return;
      }

      var person = peopleMap[email];
      try {
        var subject = a1c_buildSubject(person, weekEnd);
        var body    = a1c_buildEmail(person, areas, summaries, weekEnd);
        sendEmail(email, subject, body, 'Agent1C');
        emailsSent++;
      } catch (mailErr) {
        emailErrors++;
        Logger.log('Agent1C: Failed to send to ' + email + ' — ' + mailErr.message);
      }
    });

    notes.push('Emails sent: ' + emailsSent + ', errors: ' + emailErrors);

    // A coaching letter that never arrived is a failure of this agent's whole
    // purpose, so it must not hide inside a SUCCESS row. Anyone reading
    // AGENT_RUN_LOG has to see that N missionaries got nothing this week.
    if (quotaSkipped > 0) {
      status = 'ERROR';
      notes.push('QUOTA EXHAUSTED: ' + quotaSkipped + ' missionary/ies received NO ' +
                 'coaching letter. The main account is capped at 100 emails/day and ' +
                 'this roster needs ' + (emailsSent + quotaSkipped) + '. Configure ' +
                 'RELAY_2_URL in AGENT_CONFIG to move this agent off that quota.');
      Logger.log('Agent1C: QUOTA EXHAUSTED — ' + quotaSkipped + ' recipient(s) skipped.');
    }

    a1c_writeWeeklyBreakdowns(areas, weekEnd);
    notes.push('WEEKLY_BREAKDOWNS updated');

    a1c_recordFeedbackHistory(areas);
    notes.push('FEEDBACK_HISTORY updated');

    // Clean up Script Properties
    try { saveTempData('A1A_DATA', ''); } catch (e) {}
    try { saveTempData('A1B_DATA', ''); } catch (e) {}

    Logger.log('Agent1C: Complete — ' + notes.join(' | '));
  } catch (e) {
    status = 'ERROR';
    notes.push('ERROR: ' + e.message);
    Logger.log('Agent1C FATAL: ' + e.message + '\n' + (e.stack || ''));
  }
  logRun('Agent1C', status, null, null, null, notes.join(' | '));
}

// ─── MISSION ORG LOADER ────────────────────────────────────────────────────────
/**
 * Loads ALL active MISSION_ORG rows. Returns array of objects keyed by
 * header. Used to build the people map.
 */
/**
 * True if the relay is configured, meaning sendEmail(..., 'Agent1C') will send
 * through the relay account's UrlFetchApp quota instead of this account's
 * MailApp quota — in which case the guard in runAgent1C must not fire.
 *
 * Mirrors CCSM_AgentEscalation.ae_relayConfigured() and, more importantly,
 * sendEmail()'s own routing condition in CCSM_Helpers.gs: BOTH a URL and a
 * secret are required there, and a URL without a secret falls back to MailApp
 * with only a log line. Checking just the URL here would disable the guard for
 * a configuration that still spends the main account's quota.
 */
function a1c_relayConfigured() {
  return !!(String(getConfig('RELAY_2_URL') || '').trim() &&
            String(getConfig('RELAY_SECRET') || '').trim());
}

function a1c_loadFullMissionOrg() {
  var data = a1c_getSheetData('MISSION_ORG');
  if (!data || data.length < 2) throw new Error('MISSION_ORG empty');
  var headers = data[0].map(function(h) { return String(h).trim(); });
  var rows = [];
  for (var i = 1; i < data.length; i++) {
    var obj = {};
    headers.forEach(function(h, idx) { obj[h] = String(data[i][idx] || '').trim(); });
    if (obj['Active'].toUpperCase() !== 'TRUE' || !obj['Area_Name']) continue;
    rows.push(obj);
  }
  return rows;
}

// ─── PEOPLE MAP ────────────────────────────────────────────────────────────────
/**
 * Builds a map of email address → person profile { name, areas[], roles[] }.
 *
 * CCSM ADAPTATION (see file header note #3): CCSM's real MISSION_ORG roster
 * has no dedicated leadership-only tracking rows — Is_DL/Is_ZL/Is_STL/Is_AP/
 * Is_MP are flags directly on a companionship's own real teaching area. So,
 * unlike Provo's either/or addCompanion (area XOR role, gated on
 * a1c_isLeadershipRow), this version adds the real area AND checks the SAME
 * row's own flags for a role — a companionship holding a calling gets both
 * their personal area coaching and their leadership summary section in one
 * email. a1c_isLeadershipRow is kept only as forward-compatibility for a
 * hypothetical future dedicated tracking row (mirrors a1a_isLeadershipRow /
 * a3_isLeadershipRow); it never fires on today's roster.
 */
function a1c_buildPeopleMap(fullOrgData) {
  var people = {};

  function addCompanion(email, name, areaName, orgRow) {
    if (!email || email.indexOf('@') < 0) return;
    email = email.toLowerCase().trim();
    if (!people[email]) people[email] = { name: name, areas: [], roles: [] };

    if (!a1c_isLeadershipRow(orgRow) && areaName) {
      if (people[email].areas.indexOf(areaName) < 0) {
        people[email].areas.push(areaName);
      }
    }
    var role = a1c_getRoleFromRow(orgRow);
    if (role) people[email].roles.push(role);
  }

  fullOrgData.forEach(function(row) {
    var areaName = row['Area_Name'] || '';
    addCompanion(row['Companion1_Email'], row['Companion1_Name'], areaName, row);
    addCompanion(row['Companion2_Email'], row['Companion2_Name'], areaName, row);
  });

  return people;
}

/**
 * Determines the leadership role from a MISSION_ORG row's own flags.
 * Returns a role object: { type, zone, district } or null if none set.
 */
function a1c_getRoleFromRow(row) {
  var zone     = row['Zone']     || '';
  var district = row['District'] || '';
  if ((row['Is_MP']  || '').toUpperCase() === 'TRUE') return { type: 'MP',  zone: zone, district: district };
  if ((row['Is_AP']  || '').toUpperCase() === 'TRUE') return { type: 'AP',  zone: zone, district: district };
  if ((row['Is_ZL']  || '').toUpperCase() === 'TRUE') return { type: 'ZL',  zone: zone, district: district };
  if ((row['Is_STL'] || '').toUpperCase() === 'TRUE') return { type: 'STL', zone: zone, district: district };
  if ((row['Is_DL']  || '').toUpperCase() === 'TRUE') return { type: 'DL',  zone: zone, district: district };
  if (zone.toUpperCase() === 'ALL') return { type: 'MP', zone: zone, district: district };
  return null;
}

/**
 * Mirrors CCSM_Agent1A.gs's a1a_isLeadershipRow / CCSM_Agent3.gs's
 * a3_isLeadershipRow exactly, for consistency across the pipeline. IMOS role
 * titles (Mission President, Zone Leader, District Leader, etc.) are
 * standard English across all missions regardless of the mission's working
 * language — see CCSM_Agent1A.gs's own comment on this. No row in today's
 * CCSM_MISSION_ORG_ROWS matches; kept for forward-compatibility.
 */
function a1c_isLeadershipRow(obj) {
  if ((obj['Zone'] || '').toUpperCase() === 'ALL') return true;
  var name = String(obj['Area_Name'] || '').trim();
  if (/^(Mission President|Assistant to President|Zone Leader|Sister Training Leader -|District Leader -)/i.test(name)) return true;
  return /\bSenior\b/i.test(name);
}

// ─── EMAIL COMPOSITION ─────────────────────────────────────────────────────────
function a1c_buildSubject(person, weekEnd) {
  var weekLabel = weekEnd ? a1c_formatDate(weekEnd) : 'esta semana';
  return 'PMG Compass — Entrenamiento Semanal | ' + weekLabel;
}

/**
 * Builds the full HTML email body for one person.
 * Sections appear in order: personal area coaching, then leadership summaries.
 */
function a1c_buildEmail(person, areas, summaries, weekEnd) {
  var dateLabel = weekEnd ? a1c_formatDate(weekEnd) : 'esta semana';
  var C = {
    header:  '#1e3a5f',
    green:   '#16a34a',
    blue:    '#2563eb',
    muted:   '#6b7280',
    border:  '#e5e7eb',
    bgLight: '#f9fafb'
  };

  var html = '<div style="font-family:Arial,Helvetica,sans-serif;max-width:680px;margin:0 auto;color:#111;">';

  // Header
  html += '<div style="background:' + C.header + ';color:white;padding:20px 24px;border-radius:8px 8px 0 0;">' +
          '<div style="font-size:18px;font-weight:700;">PMG Compass — Entrenamiento Semanal</div>' +
          '<div style="font-size:12px;opacity:0.75;margin-top:4px;">Semana que termina el ' + a1c_esc(dateLabel) + '</div>' +
          '</div>';

  // Personal area coaching section
  person.areas.forEach(function(areaName) {
    var area = areas[areaName];
    if (!area) return;
    html += a1c_buildAreaSection(areaName, area, weekEnd, C);
  });

  // Leadership summary sections
  person.roles.forEach(function(role) {
    if (role.type === 'MP' || role.type === 'AP') {
      html += a1c_buildLeadershipSection(
        'Resumen de la Misión', summaries.mission, areas, 'mission', weekEnd, C
      );
      // Dashboard link — AP and MP only
      var dashUrl = getConfig('STREAMLIT_URL');
      if (dashUrl && dashUrl.trim()) {
        html += '<div style="text-align:center;margin:20px 0;">' +
                '<a href="' + dashUrl.trim() + '" style="display:inline-block;background:#1e3a5f;color:white;' +
                'padding:10px 24px;border-radius:6px;font-size:13px;font-weight:700;text-decoration:none;">' +
                'Ver el Panel de PMG Compass</a></div>';
      }
    } else if (role.type === 'ZL' || role.type === 'STL') {
      var zoneData = summaries.zones && summaries.zones[role.zone];
      html += a1c_buildLeadershipSection(
        'Resumen de Zona — ' + role.zone, zoneData, areas, 'zone', weekEnd, C, role.zone
      );
    } else if (role.type === 'DL') {
      var distData = summaries.districts && summaries.districts[role.district];
      html += a1c_buildLeadershipSection(
        'Resumen de Distrito — ' + role.district, distData, areas, 'district', weekEnd, C, null, role.district
      );
    }
  });

  // Footer
  html += '<div style="margin-top:24px;padding:12px 16px;background:' + C.bgLight + ';border-radius:0 0 8px 8px;' +
          'font-size:11px;color:' + C.muted + ';text-align:center;">' +
          'PMG Compass — ' + a1c_esc(getMissionName()) +
          '</div>';

  html += '</div>';
  return html;
}

/**
 * Numbers line for a strength/growth message block:
 *   "58% (meta 50%)  ▲ subió de 44% la semana pasada"  (+ prom. de transfer on growth)
 * Arrows: ▲ green #16a34a, ▼ amber #b45309 (never red), — muted.
 */
function a1c_statLine_(pick, derived, isGrowth) {
  if (!pick) return '';
  var key = pick.key;
  var cur  = a1c_fmtMetricVal_(key, pick.actual);
  var goal = a1c_fmtMetricVal_(key, pick.goal);
  var html = '<div style="font-size:12px;color:#374151;margin-bottom:6px;"><strong>' +
             a1c_esc(cur) + '</strong> (meta ' + a1c_esc(goal) + ')';
  var lastV = derived && derived.lastWeek ? derived.lastWeek[key] : null;
  if (lastV !== null && lastV !== undefined) {
    var diff = pick.actual - lastV;
    if (diff > 0)      html += ' &nbsp;<span style="color:#16a34a;font-weight:700;">▲ subió de ' + a1c_esc(a1c_fmtMetricVal_(key, lastV)) + ' la semana pasada</span>';
    else if (diff < 0) html += ' &nbsp;<span style="color:#b45309;font-weight:700;">▼ bajó de ' + a1c_esc(a1c_fmtMetricVal_(key, lastV)) + ' la semana pasada</span>';
    else               html += ' &nbsp;<span style="color:#6b7280;">— igual que la semana pasada</span>';
  }
  if (isGrowth && derived && derived.xferAvg && derived.xferAvg[key] !== null && derived.xferAvg[key] !== undefined) {
    html += ' &nbsp;·&nbsp; prom. del transfer ' + a1c_esc(a1c_fmtMetricVal_(key, derived.xferAvg[key]));
  }
  html += '</div>';
  return html;
}

/**
 * Goal-progress bar for a strength/growth pick: blue fill + "X% de la meta"
 * while short, green + "Meta alcanzada ✓" once actual >= goal. No bar when
 * the goal is missing/<=0 (a goal of 0 is "nothing expected" territory, not
 * a real target to show progress against).
 */
function a1c_buildGoalBar_(pick, C) {
  if (!pick) return '';
  var goal   = parseFloat(pick.goal);
  var actual = parseFloat(pick.actual);
  if (isNaN(goal) || goal <= 0 || isNaN(actual)) return '';
  var pct = Math.round(actual / goal * 100);
  if (pct < 0) pct = 0;
  var reached  = pct >= 100;
  var widthPct = reached ? 100 : pct;
  var fill  = reached ? C.green : C.blue;
  var label = reached ? 'Meta alcanzada ✓' : pct + '% de la meta';
  var html = '<div style="margin:2px 0 8px;">';
  html += '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><tr>' +
          '<td style="background:' + C.border + ';border-radius:5px;padding:0;">' +
          '<div style="width:' + widthPct + '%;background:' + fill + ';height:10px;border-radius:5px;"></div>' +
          '</td></tr></table>';
  html += '<div style="font-size:10px;color:#374151;margin-top:3px;">' +
          '<strong style="color:' + fill + ';">' + a1c_esc(label) + '</strong>' +
          ' &nbsp;·&nbsp; meta ' + a1c_esc(a1c_fmtMetricVal_(pick.key, goal)) + '</div>';
  html += '</div>';
  return html;
}

/** Area header: name + days-reported chip + streak (from area.derived.consistency). */
function a1c_buildAreaHeader_(areaName, area, C) {
  var der  = area.derived;
  var cons = der && der.consistency;
  var html = '<div style="margin:0 0 8px;">' +
    '<div style="font-size:16px;font-weight:700;color:' + C.header + ';">' + a1c_esc(areaName) + '</div>';
  if (cons) {
    var days = cons.daysReported;
    var col  = days >= 7 ? '#16a34a' : (days >= 5 ? '#b45309' : '#6b7280');
    html += '<div style="font-size:11px;color:' + C.muted + ';margin-top:3px;">' +
      '✓ <strong style="color:' + col + ';">' + days + '/7 días reportados</strong>';
    if (cons.streak > 1) html += ' &nbsp;·&nbsp; 🔥 racha de ' + cons.streak + ' días de reporte nocturno';
    html += '</div>';
    if (days > 0 && days < 7) {
      html += '<div style="font-size:10px;color:' + C.muted + ';margin-top:2px;">' +
        'Los totales abajo reflejan los ' + days + ' día' + (days > 1 ? 's' : '') + ' reportados.</div>';
    }
  }
  html += '</div>';
  return html;
}

/**
 * Builds the personal area coaching section: header (with days-reported
 * chip), 2 strength messages, 1 growth message — each now carrying its own
 * numbers line + goal bar (see the "PERSONAL-SECTION NUMBERS" note above
 * A1C_PERCENT_METRIC_KEYS) — then the growth metric's trend chart, the full
 * scoreboard, and the goal grid.
 */
function a1c_buildAreaSection(areaName, area, weekEnd, C) {
  var s   = area.strength1;
  var s2  = area.strength2;
  var g   = area.growth;
  var der = area.derived;

  var html = '<div style="margin:16px 0;padding:0 4px;">';
  html += a1c_buildAreaHeader_(areaName, area, C);

  if (s)  html += a1c_buildMessageBlock('💪 Fortaleza — ' + a1c_esc(s.display),  area.msg_strength1, C, C.green,
                                         a1c_statLine_(s, der, false) + a1c_buildGoalBar_(s, C));
  if (s2) html += a1c_buildMessageBlock('💪 Fortaleza — ' + a1c_esc(s2.display), area.msg_strength2, C, C.green,
                                         a1c_statLine_(s2, der, false) + a1c_buildGoalBar_(s2, C));
  if (g)  html += a1c_buildMessageBlock('📈 Área de Crecimiento — ' + a1c_esc(g.display), area.msg_growth, C, C.blue,
                                         a1c_statLine_(g, der, true) + a1c_buildGoalBar_(g, C));

  html += a1c_buildYouVsYou_(g, der, C);
  html += a1c_buildTrendChart_(der && der.trend, C);
  html += a1c_buildScoreboard_(area.stats, der, C, weekEnd);
  html += a1c_buildGoalGrid_(area.ranked, C, weekEnd);
  html += a1c_buildFunnelStrip_(der && der.funnel, C, weekEnd);

  html += '</div>';
  html += '<hr style="border:none;border-top:1px solid #e5e7eb;margin:8px 0;">';
  return html;
}

/**
 * 8-week bar chart for the growth metric's trend (der.trend, from
 * a1a_buildDerived). Email-safe: divs with px heights inside table cells,
 * no images. Current week in dark navy, this area's best in medium blue,
 * everything else light blue; a missing week (no report) renders a thin
 * flat line instead of a bar.
 */
function a1c_buildTrendChart_(trend, C) {
  if (!trend || !trend.series || trend.series.length === 0) return '';
  var pts = trend.series;
  var max = 0;
  pts.forEach(function(p) { if (p.value !== null && p.value > max) max = p.value; });
  if (max <= 0) return '';
  var MAXH = 56, MINH = 4;

  var html = '<div style="margin:18px 0 6px;">';
  html += '<div style="font-size:12px;font-weight:700;color:' + C.header +
          ';text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">📊 ' +
          a1c_esc(trend.display) + ' — últimas 8 semanas</div>';
  html += '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><tr>';
  var wPct = Math.floor(100 / pts.length);
  pts.forEach(function(p, i) {
    html += '<td width="' + wPct + '%" style="vertical-align:bottom;padding:0 4px;">';
    if (p.value === null) {
      html += '<div style="height:2px;background:' + C.border + ';"></div>';
    } else {
      var h = Math.max(MINH, Math.round(p.value / max * MAXH));
      var isCur  = i === pts.length - 1;
      var isBest = p.value >= max;
      var bg = isCur ? C.header : (isBest ? '#2563eb' : '#93b4d8');
      html += '<div style="height:' + h + 'px;background:' + bg + ';border-radius:3px 3px 0 0;"></div>';
    }
    html += '</td>';
  });
  html += '</tr><tr style="font-size:10px;color:#374151;text-align:center;">';
  pts.forEach(function(p) {
    var label = p.value === null ? '—' : a1c_fmtMetricVal_(trend.key, p.value) + (p.value >= max && p.value > 0 ? ' ★' : '');
    html += '<td style="padding-top:4px;font-weight:700;">' + a1c_esc(label) + '</td>';
  });
  html += '</tr><tr style="font-size:9px;color:#9ca3af;text-align:center;">';
  pts.forEach(function(p) {
    html += '<td>' + a1c_esc(a1c_shortDate_(p.week)) + '</td>';
  });
  html += '</tr></table>';
  html += '<div style="font-size:10px;color:' + C.muted + ';margin-top:5px;">★ = lo mejor de tu área · esta semana en azul marino · — = sin reporte</div>';
  html += '</div>';
  return html;
}

/**
 * "Tu Progreso Hacia la Meta — Todos los Indicadores": one compact two-bar
 * mini-chart per goaled metric (Meta track + Tú fill, 0->goal scale),
 * grouped under the same A1C_SCOREBOARD_GROUPS headers as the scoreboard.
 * Returns '' when `ranked` is empty or carries no positive goals.
 */
function a1c_buildGoalGrid_(ranked, C, weekEnd) {
  if (!ranked || ranked.length === 0) return '';

  var byKey = {};
  ranked.forEach(function(p) {
    var goal = parseFloat(p.goal), actual = parseFloat(p.actual);
    if (isNaN(goal) || goal <= 0 || isNaN(actual)) return;
    byKey[p.key] = p;
  });
  if (Object.keys(byKey).length === 0) return '';

  function chart(p) {
    var goal = parseFloat(p.goal), actual = parseFloat(p.actual);
    var pct = Math.round(actual / goal * 100);
    if (pct < 0) pct = 0;
    var reached = actual >= goal;
    var youW = reached ? 100 : Math.max(2, pct);
    var fill = reached ? C.green : C.blue;
    var caption = reached ? 'Meta alcanzada ✓' : pct + '% de la meta';
    var h = '<div style="margin:0 0 10px;">';
    h += '<div style="font-size:11px;font-weight:700;color:#374151;margin-bottom:3px;">' +
         a1c_esc(p.display) + '</div>';
    h += '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:10px;">';
    h += '<tr><td style="width:38px;color:' + C.muted + ';padding-right:6px;">Meta</td>' +
         '<td><div style="background:' + C.border + ';border-radius:5px;">' +
         '<div style="width:100%;background:#c7d2e0;height:9px;border-radius:5px;font-size:1px;line-height:1px;">&nbsp;</div></div></td>' +
         '<td style="width:52px;text-align:right;padding-left:6px;color:#374151;font-weight:700;">' +
         a1c_esc(a1c_fmtMetricVal_(p.key, goal)) + '</td></tr>';
    h += '<tr><td style="width:38px;color:' + C.muted + ';padding-right:6px;padding-top:2px;">Tú</td>' +
         '<td style="padding-top:2px;"><div style="background:' + C.border + ';border-radius:5px;">' +
         '<div style="width:' + youW + '%;background:' + fill + ';height:9px;border-radius:5px;font-size:1px;line-height:1px;">&nbsp;</div></div></td>' +
         '<td style="width:52px;text-align:right;padding-left:6px;padding-top:2px;color:' + fill + ';font-weight:700;">' +
         a1c_esc(a1c_fmtMetricVal_(p.key, actual)) + '</td></tr>';
    h += '</table>';
    h += '<div style="font-size:9px;color:' + C.muted + ';margin-top:1px;">' + a1c_esc(caption) + '</div>';
    h += '</div>';
    return h;
  }

  var claimed = {};
  A1C_SCOREBOARD_GROUPS.forEach(function(gr) { gr.keys.forEach(function(k) { claimed[k] = 1; }); });
  var extras = Object.keys(byKey).filter(function(k) { return !claimed[k]; }).sort();
  var groups = A1C_SCOREBOARD_GROUPS.slice();
  if (extras.length > 0) groups.push({ title: '📦 OTROS — Formulario Nocturno', keys: extras });

  var html = '<div style="margin:16px 0;">';
  html += '<div style="font-size:12px;font-weight:700;color:' + C.header +
          ';text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px;">' +
          a1c_esc(a1c_saltTitle_('Tu Progreso Hacia la Meta — Todos los Indicadores', weekEnd)) + '</div>';
  groups.forEach(function(gr) {
    var present = gr.keys.filter(function(k) { return byKey[k]; });
    if (present.length === 0) return;
    html += '<div style="font-size:10px;font-weight:700;color:' + C.header +
            ';background:#dbeafe;padding:4px 8px;border-radius:4px;margin:8px 0;">' + a1c_esc(gr.title) + '</div>';
    present.forEach(function(k) { html += chart(byKey[k]); });
  });
  html += '</div>';
  return html;
}

/**
 * "Tu contra Ti" — horizontal comparison bars for the growth metric: Esta
 * Semana / Semana Pasada / Prom. Transfer / Tu Mejor on a shared baseline.
 * Comparing a missionary against their OWN history is the motivator (never
 * area-vs-area). Null values render '—' with no bar; all-null/zero history
 * renders nothing.
 */
function a1c_buildYouVsYou_(pick, derived, C) {
  if (!pick) return '';
  var key = pick.key;
  function pull(map) {
    if (!derived || !map) return null;
    var v = map[key];
    return (v === null || v === undefined) ? null : v;
  }
  var rows = [
    { label: 'Esta Semana',    value: (pick.actual === null || pick.actual === undefined) ? null : pick.actual, color: C.header },
    { label: 'Semana Pasada',  value: pull(derived && derived.lastWeek), color: '#93b4d8' },
    { label: 'Prom. Transfer', value: pull(derived && derived.xferAvg),  color: '#93b4d8' },
    { label: 'Tu Mejor',       value: pull(derived && derived.best),     color: '#2563eb' }
  ];
  var max = 0;
  rows.forEach(function(r) { if (r.value !== null && r.value > max) max = r.value; });
  if (max <= 0) return '';

  var html = '<div style="margin:14px 0 6px;">';
  html += '<div style="font-size:12px;font-weight:700;color:' + C.header +
          ';text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">🆚 Tú contra Ti — ' +
          a1c_esc(pick.display) + '</div>';
  html += '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:11px;">';
  rows.forEach(function(r) {
    html += '<tr><td style="padding:3px 8px 3px 0;color:#374151;white-space:nowrap;width:90px;">' +
            a1c_esc(r.label) + '</td>';
    if (r.value === null) {
      html += '<td style="padding:3px 0;color:' + C.muted + ';">—</td>';
    } else {
      var w = Math.max(2, Math.round(r.value / max * 100));
      html += '<td style="padding:3px 0;">' +
              '<div style="width:' + w + '%;background:' + r.color + ';height:12px;border-radius:3px;display:inline-block;vertical-align:middle;"></div>' +
              '<span style="padding-left:6px;font-weight:700;color:#374151;">' +
              a1c_esc(a1c_fmtMetricVal_(key, r.value)) + '</span></td>';
    }
    html += '</tr>';
  });
  html += '</table></div>';
  return html;
}

/**
 * "Tu Embudo Esta Semana" — CCSM's real nightly funnel (attempted -> made ->
 * meaningful -> lessons -> new friends found), from area.derived.funnel (see
 * a1a_buildDerived's funnel remap). No LSI tile/note at all — CCSM's form
 * has no LSI metric, unlike Provo's version this was ported from.
 */
function a1c_buildFunnelStrip_(f, C, weekEnd) {
  if (!f) return '';
  function tile(val, label, hl) {
    return '<td style="background:' + (hl ? '#eafaf0' : '#f0f4f8') + ';border-radius:6px;padding:8px 6px;text-align:center;' + (hl ? 'border:1px solid #16a34a;' : '') + '">' +
      '<div style="font-size:16px;font-weight:700;color:' + (hl ? '#15803d' : C.header) + ';">' + a1c_esc(String(val)) + '</div>' +
      '<div style="font-size:9px;color:' + (hl ? '#15803d' : C.muted) + ';text-transform:uppercase;">' + a1c_esc(label) + '</div></td>';
  }
  function arrow(p) {
    return '<td style="width:34px;text-align:center;font-size:9px;color:#16a34a;font-weight:700;">→<br>' + (p === null ? '—' : p + '%') + '</td>';
  }
  var html = '<div style="margin:18px 0;">';
  html += '<div style="font-size:12px;font-weight:700;color:' + C.header +
          ';text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">🔄 ' + a1c_esc(a1c_saltTitle_('Tu Embudo Esta Semana', weekEnd)) + '</div>';
  html += '<table width="100%" cellpadding="0" cellspacing="0"><tr>' +
    tile(f.attempted, 'Intentados') + arrow(f.contactedPct) +
    tile(f.contacted, 'Contactos') + arrow(f.meaningfulPct) +
    tile(f.meaningful, 'Significativas') + arrow(f.lessonPct) +
    tile(f.lessons, 'Lecciones') + arrow(f.newFoundPct) +
    tile(f.newFound, 'Nuevas Amistades', true) +
    '</tr></table>';
  if (f.lessonsPerNewFriend !== null) {
    html += '<div style="font-size:10px;color:' + C.muted + ';margin-top:6px;">' +
            f.lessonsPerNewFriend + ' lecciones por cada nueva amistad encontrada</div>';
  }
  html += '</div>';
  return html;
}

/**
 * Renders one coaching message block (subject, body, PMG page, scripture).
 * All text comes directly from MESSAGE_BANK (via getMessageBank()'s camelCase
 * shape — see file header note #2) or from _LEADERSHIP_MSGS — nothing here
 * is AI-generated. `numbersHtml` (stat line + goal bar) is optional and
 * renders directly under the label, above the quoted message.
 */
function a1c_buildMessageBlock(label, msg, C, accentColor, numbersHtml) {
  if (!msg) return '';
  var body       = a1c_esc(msg.bodyText       || '');
  var subject    = a1c_esc(msg.subjectLine    || '');
  var pmgRef     = a1c_formatPmgRef(msg.pmgPage);
  var pmgDesc    = a1c_esc(msg.pmgDescription || '');
  var scripture  = a1c_esc(msg.scripture      || '');
  var scriptText = a1c_esc(msg.scriptureText  || '');

  var html = '<div style="border-left:4px solid ' + accentColor + ';padding:10px 14px;margin:10px 0;background:#fafafa;">';
  html += '<div style="font-size:12px;font-weight:700;color:' + accentColor + ';margin-bottom:6px;">' + label + '</div>';
  if (numbersHtml) html += numbersHtml;
  if (subject) html += '<div style="font-style:italic;font-size:13px;margin-bottom:6px;color:#374151;">"' + subject + '"</div>';
  if (body)    html += '<div style="font-size:13px;line-height:1.6;color:#1f2937;">' + body.replace(/\n/g, '<br>') + '</div>';
  if (pmgRef || scripture) {
    html += '<div style="margin-top:10px;font-size:11px;color:' + C.muted + ';">';
    if (pmgRef)    html += '📖 <strong>' + a1c_esc(pmgRef) + '</strong>' + (pmgDesc ? ' — ' + pmgDesc : '');
    if (scripture) html += (pmgRef ? '&nbsp;&nbsp;|&nbsp;&nbsp;' : '') + '✏️ ' + scripture;
    if (scriptText) html += '<div style="font-style:italic;margin-top:3px;">' + scriptText + '</div>';
    html += '</div>';
  }
  html += '</div>';
  return html;
}

/**
 * "Tu Semana — Todos los Indicadores": full metrics table (this week / last
 * week / delta / transfer avg / best) grouped Buscar/Ensenar/Invitar, plus a
 * tiny this-week-vs-best bar under each value. CCSM analogue of Provo's
 * docs/Agent1C.gs a1c_buildScoreboard_ — see A1C_SCOREBOARD_GROUPS above for
 * the CCSM-specific grouping and metric set.
 */
function a1c_buildScoreboard_(stats, der, C, weekEnd) {
  if (!der || !stats) return '';
  function cell(v, al, extra) {
    return '<td style="padding:4px 6px;text-align:' + (al || 'center') + ';border-bottom:1px solid ' + C.border + ';' + (extra || '') + '">' + v + '</td>';
  }
  function deltaCell(key) {
    var dv = der.delta ? der.delta[key] : null;
    if (dv === null || dv === undefined) return cell('—', 'center', 'color:' + C.muted + ';');
    var isPct = A1C_PERCENT_METRIC_KEYS.indexOf(key) !== -1;
    var mag = isPct ? Math.round(Math.abs(dv) * 100) : (key === 'effort_score' ? Math.abs(dv) : Math.round(Math.abs(dv)));
    if (dv > 0) return cell('▲ +' + mag, 'center', 'color:#16a34a;font-weight:700;');
    if (dv < 0) return cell('▼ −' + mag, 'center', 'color:#b45309;font-weight:700;');
    return cell('—', 'center', 'color:' + C.muted + ';');
  }
  // Tiny This-Wk-vs-Best bar under the value: position on a common scale is
  // the easiest visual to read. No bar when Best is unknown (no fake zeros).
  function miniBar(key) {
    var thisWk = stats[key];
    var best = der.best ? der.best[key] : null;
    if (typeof thisWk !== 'number' || typeof best !== 'number' || best <= 0) return '';
    var w = thisWk <= 0 ? 0 : Math.max(2, Math.min(100, Math.round(thisWk / best * 100)));
    return '<div style="background:' + C.border + ';border-radius:2px;margin-top:2px;">' +
           '<div style="width:' + w + '%;background:' + C.blue + ';height:4px;border-radius:2px;font-size:1px;line-height:1px;">&nbsp;</div></div>';
  }
  function row(key, idx) {
    var label = a1c_scoreboardLabel_(key);
    var bg = idx % 2 === 0 ? '#ffffff' : C.bgLight;
    var bestMark = der.isBest && der.isBest[key] ? ' ★' : '';
    return '<tr style="background:' + bg + ';">' +
      cell(a1c_esc(label), 'left') +
      cell('<strong>' + a1c_esc(a1c_fmtMetricVal_(key, stats[key])) + bestMark + '</strong>' + miniBar(key)) +
      cell('<span style="color:' + C.muted + ';">' + a1c_esc(a1c_fmtMetricVal_(key, der.lastWeek ? der.lastWeek[key] : null)) + '</span>') +
      deltaCell(key) +
      cell(a1c_esc(a1c_fmtMetricVal_(key, der.xferAvg ? der.xferAvg[key] : null))) +
      cell(a1c_esc(a1c_fmtMetricVal_(key, der.best ? der.best[key] : null))) +
      '</tr>';
  }

  var claimed = { submissions: 1, effort_all: 1, effort_most: 1, effort_some: 1, effort_total: 1, effort_score: 1 };
  A1C_SCOREBOARD_GROUPS.forEach(function(gr) { gr.keys.forEach(function(k) { claimed[k] = 1; }); });
  var extras = [];
  Object.keys(stats).forEach(function(k) {
    if (claimed[k]) return;
    if (typeof stats[k] === 'number') extras.push(k);
  });

  var html = '<div style="margin:16px 0;">';
  html += '<div style="font-size:12px;font-weight:700;color:' + C.header +
          ';text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">' +
          a1c_esc(a1c_saltTitle_('Tu Semana — Todos los Indicadores', weekEnd)) + '</div>';
  html += '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:11px;">';
  html += '<tr style="background:' + C.header + ';color:#ffffff;">' +
    '<th style="padding:5px 8px;text-align:left;font-size:10px;">Indicador</th>' +
    '<th style="padding:5px 6px;text-align:center;font-size:10px;">Esta Sem</th>' +
    '<th style="padding:5px 6px;text-align:center;font-size:10px;">Sem Pasada</th>' +
    '<th style="padding:5px 6px;text-align:center;font-size:10px;">Δ</th>' +
    '<th style="padding:5px 6px;text-align:center;font-size:10px;">Prom Transfer</th>' +
    '<th style="padding:5px 6px;text-align:center;font-size:10px;">Mejor</th></tr>';

  var groups = A1C_SCOREBOARD_GROUPS.slice();
  if (extras.length > 0) groups.push({ title: '📦 OTROS — Formulario Nocturno', keys: extras.sort() });
  groups.forEach(function(gr) {
    var present = gr.keys.filter(function(k) { return stats[k] !== undefined; });
    if (present.length === 0) return;
    html += '<tr><td colspan="6" style="padding:5px 8px;background:#dbeafe;font-weight:700;font-size:10px;color:' + C.header + ';">' + gr.title + '</td></tr>';
    present.forEach(function(k, idx) { html += row(k, idx); });
  });
  html += '</table></div>';
  return html;
}

// ─── LEADERSHIP SECTION ────────────────────────────────────────────────────────
/**
 * Builds a leadership summary section:
 *   1. Gemini-generated Christlike coaching narrative
 *   2. KPI tiles strip
 *   3. Area data table — district-grouped with subtotals for zone scope
 *   4. Per-area detail panel (zone/district scope only)
 *   5. Human-curated leadership coaching message
 */
function a1c_buildLeadershipSection(title, summaryTotals, areas, scope, weekEnd, C, filterZone, filterDistrict) {
  var html = '<div style="margin:20px 0;">';
  html += '<div style="font-size:15px;font-weight:700;color:' + C.header + ';padding-bottom:6px;' +
          'border-bottom:2px solid ' + C.header + ';margin-bottom:12px;">' +
          a1c_esc(title) + '</div>';

  var unitName = scope === 'mission' ? getMissionName()
               : scope === 'zone'    ? (filterZone     || 'Zona')
               :                       (filterDistrict || 'Distrito');

  var areaDetails = [];
  Object.keys(areas).sort().forEach(function(areaName) {
    var area = areas[areaName];
    if (scope === 'zone'     && area.zone     !== filterZone)     return;
    if (scope === 'district' && area.district !== filterDistrict) return;
    areaDetails.push({
      name:      areaName,
      stats:     area.stats     || {},
      zone:      area.zone      || '',
      district:  area.district  || '',
      growth:    area.growth    || null,
      strength1: area.strength1 || null,
      strength2: area.strength2 || null
    });
  });

  var narrative = a1c_buildLeadershipNarrative(scope, unitName, summaryTotals, areaDetails, weekEnd, C);
  if (narrative) html += narrative;

  html += a1c_buildKpiTiles_(summaryTotals, C);
  html += a1c_buildAreaDataTable_(areaDetails, scope, C);
  if (scope !== 'mission') {
    html += a1c_buildAreaDetailPanel_(areaDetails, scope, C);
  }

  var lMsg = a1c_pickRelevantLeadershipMsg_(summaryTotals, areaDetails);
  if (lMsg) {
    html += '<div style="margin-top:4px;">';
    html += a1c_buildMessageBlock(
      '📋 Coaching de Liderazgo — ' + a1c_esc(lMsg.theme),
      {
        subjectLine:    lMsg.subject,
        bodyText:       lMsg.body,
        pmgPage:        lMsg.pmg,
        pmgDescription: '',
        scripture:      lMsg.scripture,
        scriptureText:  lMsg.scriptText
      },
      C,
      C.header
    );
    html += '</div>';
  }

  html += '</div>';
  return html;
}

/**
 * Picks a leadership coaching message whose theme matches the zone/district's
 * actual data:
 *   1. Low submission rate (<75%)      → Cultura de Zona
 *   2. Most common area growth focus   → Buscar / Enseñar / Indicadores Clave / Cultura de Zona
 *   3. Fallback                        → Fe
 * Growth-key groupings mirror CCSM's actual metric set (A1A_RATE_METRICS +
 * QUESTIONS_CONFIG NIGHTLY NUMBER keys) — see file header note #1.
 */
function a1c_pickRelevantLeadershipMsg_(summaryTotals, areaDetails) {
  if (!_LEADERSHIP_MSGS || _LEADERSHIP_MSGS.length === 0) return null;

  var theme = 'Fe';
  var totals  = summaryTotals || {};
  var submPct = totals.total_areas > 0 ? (totals.submitted || 0) / totals.total_areas : 1;

  if (submPct < 0.75) {
    theme = 'Cultura de Zona';
  } else {
    var findingKeys  = ['contact_rate', 'new_people_found', 'references_asked', 'member_referrals_received', 'bom_shared'];
    var teachingKeys = ['mc_rate', 'lesson_rate', 'friend_lessons', 'lessons_member_present', 'pmf_lessons', 'rc_lessons', 'rc_lessons_mcp'];
    var kiKeys       = ['close_rate', 'baptismal_invitations', 'baptism_doctrine_lessons', 'baptismal_calendars', 'church_invites'];
    var cultureKeys  = ['effort_score', 'roleplays'];

    var counts = { 'Buscar': 0, 'Enseñar': 0, 'Indicadores Clave': 0, 'Cultura de Zona': 0 };
    (areaDetails || []).forEach(function(aObj) {
      var gKey = aObj.growth && aObj.growth.key;
      if (!gKey) return;
      if (findingKeys.indexOf(gKey)  >= 0) counts['Buscar']++;
      else if (teachingKeys.indexOf(gKey) >= 0) counts['Enseñar']++;
      else if (kiKeys.indexOf(gKey)       >= 0) counts['Indicadores Clave']++;
      else if (cultureKeys.indexOf(gKey)  >= 0) counts['Cultura de Zona']++;
    });

    var best = 0;
    Object.keys(counts).forEach(function(t) { if (counts[t] > best) { best = counts[t]; theme = t; } });
    if (best === 0) theme = 'Fe';
  }

  var matching = _LEADERSHIP_MSGS.filter(function(m) { return m.theme === theme; });
  if (matching.length === 0) matching = _LEADERSHIP_MSGS;
  return matching[Math.floor(Math.random() * matching.length)];
}

/**
 * 2-row, 4-column KPI tile strip for leadership emails, drawn from CCSM's
 * real dynamic count-metric totals (a1a_buildSummaries accumulates every
 * numeric stat key across areas).
 */
function a1c_buildKpiTiles_(totals, C) {
  if (!totals) return '';
  var t       = totals;
  var submPct = t.total_areas > 0 ? Math.round((t.submitted || 0) / t.total_areas * 100) : 0;

  function tile(val, label, bg) {
    return '<td style="width:25%;padding:3px;">' +
      '<div style="background:' + bg + ';border-radius:6px;padding:10px 4px;text-align:center;">' +
      '<div style="font-size:19px;font-weight:700;line-height:1.1;color:#ffffff;">' +
        a1c_esc(String(val !== undefined && val !== null ? val : '—')) +
      '</div>' +
      '<div style="font-size:9px;text-transform:uppercase;letter-spacing:0.05em;margin-top:3px;color:#ffffff;opacity:0.85;">' +
        a1c_esc(label) +
      '</div>' +
      '</div></td>';
  }

  var submLabel = (t.submitted || 0) + ' / ' + (t.total_areas || 0) + ' (' + submPct + '%)';
  var html = '<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 12px 0;">';
  html += '<tr>';
  html += tile(submLabel,                              'Reportaron',        '#374151');
  html += tile(t.contacts_made             || 0,        'Contactos',        C.header);
  html += tile(t.meaningful_conversations  || 0,        'Significativas',   '#7c3aed');
  html += tile(t.new_people_found          || 0,        'Nuevas',           '#2563eb');
  html += '</tr><tr>';
  html += tile(t.friend_lessons            || 0,        'Lecciones',        '#0f766e');
  html += tile(t.baptismal_invitations     || 0,        'Inv. Bautismo',    '#b45309');
  html += tile(t.bom_shared                || 0,        'Libros Entreg.',   '#475569');
  html += tile(t.baptism_doctrine_lessons  || 0,        'Doctrina Baut.',   '#15803d');
  html += '</tr>';
  html += '</table>';
  return html;
}

/**
 * Area data table for leadership emails.
 * zone scope     — areas grouped by district with district subtotals + zone total row.
 * district scope — flat area list with district total row.
 * mission scope  — flat area list with Zone column + mission total row.
 */
function a1c_buildAreaDataTable_(areaDetails, scope, C) {
  var isMission = scope === 'mission';
  var isZone    = scope === 'zone';

  var cols = [{ h: 'Área', key: 'name', al: 'left' }];
  if (isMission) cols.push({ h: 'Zona', key: 'zone', al: 'left' });
  A1C_TABLE_METRICS.forEach(function(m) { cols.push({ h: m.label, key: m.key, al: 'center' }); });
  cols.push({ h: 'Esf.', key: 'effort_score', al: 'center' });
  cols.push({ h: '✓', key: 'submitted', al: 'center' });

  function statVal(s, key) {
    if (key === 'submitted')    return (s.submissions || 0) > 0 ? '✓' : '—';
    if (key === 'effort_score') return a1c_formatMetricValue('effort_score', s.effort_score);
    return s[key] || 0;
  }

  function numVal(s, key) {
    if (key === 'effort_score') return 0; // not summable — excluded from totals
    return s[key] || 0;
  }

  var metricCols = cols.filter(function(c) {
    return c.key !== 'name' && c.key !== 'zone' && c.key !== 'submitted';
  });

  function makeHeaderRow() {
    var row = '<tr style="background:' + C.header + ';color:white;">';
    cols.forEach(function(c) {
      row += '<th style="padding:5px 6px;text-align:' + c.al + ';white-space:nowrap;font-size:10px;">' +
             a1c_esc(c.h) + '</th>';
    });
    return row + '</tr>';
  }

  function makeTotalRow(labelText, totMap, submCount, totalCount, rowStyle) {
    var row = '<tr style="' + rowStyle + '">';
    cols.forEach(function(c) {
      var v;
      if      (c.key === 'name')         v = labelText;
      else if (c.key === 'zone')         v = '';
      else if (c.key === 'submitted')    v = submCount + '/' + totalCount;
      else if (c.key === 'effort_score') v = '—';
      else                                v = totMap[c.key] || 0;
      row += '<td style="padding:4px 6px;text-align:' + c.al + ';white-space:nowrap;">' +
             a1c_esc(String(v)) + '</td>';
    });
    return row + '</tr>';
  }

  var tableFontSize = isMission ? '10px' : '9px';
  var html = '<table style="width:100%;border-collapse:collapse;font-size:' + tableFontSize + ';margin-bottom:8px;">';
  html += makeHeaderRow();

  if (isZone) {
    var byDist = {};
    var distOrder = [];
    areaDetails.forEach(function(a) {
      var d = a.district || 'Sin Asignar';
      if (!byDist[d]) { byDist[d] = []; distOrder.push(d); }
      byDist[d].push(a);
    });
    distOrder.sort();

    var zoneTot = {}; var zoneSubm = 0;
    metricCols.forEach(function(c) { zoneTot[c.key] = 0; });

    distOrder.forEach(function(dist) {
      var dAreas = byDist[dist].slice().sort(function(a, b) { return a.name < b.name ? -1 : 1; });
      var dTot   = {}; var dSubm = 0;
      metricCols.forEach(function(c) { dTot[c.key] = 0; });

      html += '<tr style="background:#dbeafe;">';
      html += '<td colspan="' + cols.length + '" style="padding:4px 6px;font-weight:700;font-size:10px;color:#1e3a5f;">' +
              '📍 Distrito ' + a1c_esc(dist) + '</td>';
      html += '</tr>';

      dAreas.forEach(function(aObj, idx) {
        var s  = aObj.stats;
        var bg = idx % 2 === 0 ? '#ffffff' : C.bgLight;
        html += '<tr style="background:' + bg + ';">';
        cols.forEach(function(c) {
          var v = c.key === 'name' ? aObj.name
                : c.key === 'zone' ? aObj.zone
                : statVal(s, c.key);
          html += '<td style="padding:3px 6px;text-align:' + c.al + ';border-bottom:1px solid ' + C.border + ';white-space:nowrap;">' +
                  a1c_esc(String(v !== undefined && v !== null ? v : '—')) + '</td>';
        });
        html += '</tr>';
        metricCols.forEach(function(c) {
          dTot[c.key] += numVal(s, c.key);
          zoneTot[c.key] += numVal(s, c.key);
        });
        if ((s.submissions || 0) > 0) { dSubm++; zoneSubm++; }
      });

      html += makeTotalRow(
        dist + ' Total', dTot, dSubm, dAreas.length,
        'background:#eff6ff;font-weight:700;color:#1e3a5f;border-top:1px solid #bfdbfe;'
      );
    });

    html += makeTotalRow(
      'TOTAL DE ZONA', zoneTot, zoneSubm, areaDetails.length,
      'background:' + C.header + ';color:white;font-weight:700;'
    );

  } else {
    var flatTot = {}; var flatSubm = 0;
    metricCols.forEach(function(c) { flatTot[c.key] = 0; });

    areaDetails.forEach(function(aObj, idx) {
      var s  = aObj.stats;
      var bg = idx % 2 === 0 ? '#ffffff' : C.bgLight;
      html += '<tr style="background:' + bg + ';">';
      cols.forEach(function(c) {
        var v = c.key === 'name' ? aObj.name
              : c.key === 'zone' ? aObj.zone
              : statVal(s, c.key);
        html += '<td style="padding:3px 6px;text-align:' + c.al + ';border-bottom:1px solid ' + C.border + ';white-space:nowrap;">' +
                a1c_esc(String(v !== undefined && v !== null ? v : '—')) + '</td>';
      });
      html += '</tr>';
      metricCols.forEach(function(c) { flatTot[c.key] += numVal(s, c.key); });
      if ((s.submissions || 0) > 0) flatSubm++;
    });

    var totalLabel = isMission ? 'TOTAL DE LA MISIÓN' : 'TOTAL DE DISTRITO';
    html += makeTotalRow(
      totalLabel, flatTot, flatSubm, areaDetails.length,
      'background:' + C.header + ';color:white;font-weight:700;'
    );
  }

  html += '</table>';
  return html;
}

// ─── AREA DETAIL PANEL ────────────────────────────────────────────────────────
/**
 * Renders one coaching card per area for zone/district leadership emails,
 * covering the FULL CCSM nightly metric set (see file header note #1) —
 * contact, conversations, teaching, sharing, baptism, and effort/compliance.
 * Language rule: NEVER "investigador" — all people being taught are "amigos".
 */
function a1c_buildAreaDetailPanel_(areaDetails, scope, C) {
  if (!areaDetails || areaDetails.length === 0) return '';

  var sorted = areaDetails.slice().sort(function(a, b) {
    if (scope === 'zone') {
      var da = a.district || ''; var db = b.district || '';
      if (da !== db) return da < db ? -1 : 1;
    }
    return a.name < b.name ? -1 : 1;
  });

  var html = '<div style="margin:16px 0;">';
  html += '<div style="font-size:12px;font-weight:700;color:' + C.header +
          ';text-transform:uppercase;letter-spacing:0.05em;padding-bottom:4px;' +
          'border-bottom:2px solid ' + C.border + ';margin-bottom:10px;">' +
          'Detalle de Áreas — Métricas Completas de la Semana</div>';

  var lastDistrict = null;

  sorted.forEach(function(aObj) {
    var s         = aObj.stats;
    var g         = aObj.growth;
    var submitted = (s.submissions || 0) > 0;

    if (scope === 'zone' && aObj.district !== lastDistrict) {
      lastDistrict = aObj.district;
      html += '<div style="font-size:10px;font-weight:700;color:' + C.header +
              ';margin:10px 0 4px;padding:3px 6px;background:#dbeafe;border-radius:4px;">' +
              '📍 Distrito ' + a1c_esc(aObj.district) + '</div>';
    }

    var growthHtml = '';
    if (g) {
      var actualStr = a1c_formatMetricValue(g.key, g.actual);
      var goalStr   = a1c_formatMetricValue(g.key, g.goal);
      var pct = Math.round(g.pct * 100);
      growthHtml = '<div style="font-size:10px;color:#1d4ed8;margin:3px 0 6px;">' +
                   '📈 Área de Crecimiento: <strong>' + a1c_esc(g.display) + '</strong>' +
                   ' — ' + a1c_esc(actualStr) +
                   ' (meta: ' + a1c_esc(goalStr) + ' · ' + pct + '% de la meta)</div>';
    }

    html += '<div style="margin-bottom:8px;padding:8px 10px;background:#f9fafb;' +
            'border-left:3px solid ' + (submitted ? C.header : '#9ca3af') +
            ';border-radius:0 4px 4px 0;">';

    html += '<table width="100%" cellpadding="0" cellspacing="0"><tr>' +
            '<td style="font-size:11px;font-weight:700;color:#1f2937;">' + a1c_esc(aObj.name) + '</td>' +
            '<td style="font-size:10px;color:' + C.muted + ';text-align:right;">' +
            (submitted ? '✓ Reportó' : '⚠ Sin informe') +
            '</td></tr></table>';

    html += growthHtml;

    function section(emoji, label, pairs) {
      return '<div style="margin-top:5px;">' +
             '<div style="font-size:9px;text-transform:uppercase;letter-spacing:0.08em;' +
             'color:#9ca3af;font-weight:700;margin-bottom:2px;">' + emoji + ' ' + a1c_esc(label) + '</div>' +
             '<div style="font-size:10px;color:#374151;line-height:2.0;">' +
             pairs.map(function(p) {
               return '<span style="margin-right:14px;white-space:nowrap;">' +
                      '<span style="color:#6b7280;">' + a1c_esc(p[0]) + ':&nbsp;</span>' +
                      '<strong>' + a1c_esc(String(p[1])) + '</strong></span>';
             }).join('') + '</div></div>';
    }

    html += section('📞', 'Contacto', [
      ['Intentos',         s.contacts_attempted || 0],
      ['Contactos',        s.contacts_made       || 0],
      ['Tasa de Contacto', a1c_formatMetricValue('contact_rate', s.contact_rate)]
    ]);

    html += section('💬', 'Conversaciones', [
      ['Significativas', s.meaningful_conversations || 0],
      ['Tasa',           a1c_formatMetricValue('mc_rate', s.mc_rate)]
    ]);

    html += section('📚', 'Enseñanza', [
      ['Lecciones con Amigos',  s.friend_lessons          || 0],
      ['Con Miembro Presente',  s.lessons_member_present  || 0],
      ['Familias Parciales',    s.pmf_lessons             || 0],
      ['Conversos Recientes',   s.rc_lessons              || 0],
      ['CR (Mi Senda)',         s.rc_lessons_mcp          || 0],
      ['Tasa de Lecciones',     a1c_formatMetricValue('lesson_rate', s.lesson_rate)]
    ]);

    html += section('📱', 'Compartir', [
      ['Libros de Mormón Entreg.',   s.bom_shared                || 0],
      ['Invitaciones a la Iglesia',  s.church_invites            || 0],
      ['Referencias Solicitadas',    s.references_asked          || 0],
      ['Ref. de Miembros Recibidas', s.member_referrals_received || 0],
      ['Contactos con Miembros',     s.member_contacts           || 0]
    ]);

    html += section('📅', 'Bautismo', [
      ['Invitaciones al Bautismo', s.baptismal_invitations    || 0],
      ['Lecciones de Doctrina',    s.baptism_doctrine_lessons || 0],
      ['Calendarios Entregados',   s.baptismal_calendars      || 0],
      ['Tasa de Invitación',       a1c_formatMetricValue('close_rate', s.close_rate)]
    ]);

    html += section('💪', 'Esfuerzo y Cumplimiento', [
      ['Esfuerzo',         a1c_formatMetricValue('effort_score', s.effort_score)],
      ['Todo',             s.effort_all  || 0],
      ['La Mayor Parte',   s.effort_most || 0],
      ['Algo',             s.effort_some || 0],
      ['Días Reportados',  s.submissions || 0]
    ]);

    html += '</div>';
  });

  html += '</div>';
  return html;
}

// ─── LEADERSHIP NARRATIVE (GEMINI-GENERATED) ──────────────────────────────────
/**
 * Shared area-summary line used by both the per-unit narrative prompt
 * (a1c_buildLeadershipNarrative) and the batch narrative prompt
 * (a1c_fetchBatchNarratives_), so the two never drift out of sync.
 */
function a1c_areaSummaryLine_(a) {
  var s      = a.stats || {};
  var gFocus = (a.growth && a.growth.display) ? a.growth.display : '';
  return a.name +
    ' | Contactos: '                     + (s.contacts_made             || 0) +
    ' | Conversaciones Significativas: ' + (s.meaningful_conversations  || 0) +
    ' | Nuevas Personas: '               + (s.new_people_found          || 0) +
    ' | Lecciones con Amigos: '          + (s.friend_lessons            || 0) +
    ' | Invitaciones al Bautismo: '      + (s.baptismal_invitations     || 0) +
    ' | Tasa de Contacto: '              + a1c_formatMetricValue('contact_rate', s.contact_rate) +
    ' | Tasa de Conversaciones: '        + a1c_formatMetricValue('mc_rate', s.mc_rate) +
    ' | Esfuerzo: '                      + a1c_formatMetricValue('effort_score', s.effort_score) +
    (gFocus ? ' | Área de Crecimiento: ' + gFocus : '') +
    ' | Reportó: ' + ((s.submissions || 0) > 0 ? 'Sí' : 'No');
}

/**
 * Calls Gemini to generate a Christlike coaching paragraph for a leadership
 * level. Returns an HTML string to inject above the data table, or '' on
 * any error (table still renders without it).
 *
 * Language rules enforced in the prompt: NEVER "investigador" — always
 * "amigos"; Christlike tone; no negative comparisons or shaming; append the
 * required Spanish-output instruction; use getMissionName() (never a
 * hardcoded mission name literal) — see file header note.
 */
function a1c_buildLeadershipNarrative(scope, unitName, summaryData, areaDetails, weekEnd, C) {
  var cacheKey = scope + ':' + unitName;
  if (_narrativeCache[cacheKey]) return a1c_renderNarrativeHtml_(_narrativeCache[cacheKey], C);

  try {
    var dateLabel = weekEnd ? a1c_formatDate(weekEnd) : 'esta semana';
    var totals    = summaryData || {};
    var areaLines = areaDetails.map(a1c_areaSummaryLine_).join('\n');

    var prompt = [
      'Eres un asistente de análisis de misión para la ' + getMissionName() + '.',
      'Semana que termina: ' + dateLabel,
      'Alcance: ' + scope + ' — ' + unitName,
      '',
      'Estadísticas agregadas para este ' + scope + ':',
      '- Áreas que reportaron: '           + (totals.submitted               || 0) + ' / ' + (totals.total_areas || 0),
      '- Contactos: '                      + (totals.contacts_made           || 0),
      '- Conversaciones Significativas: '  + (totals.meaningful_conversations|| 0),
      '- Nuevas Personas Encontradas: '    + (totals.new_people_found        || 0),
      '- Lecciones con Amigos: '           + (totals.friend_lessons          || 0),
      '- Invitaciones al Bautismo: '       + (totals.baptismal_invitations   || 0),
      '',
      'Desglose por área:',
      areaLines,
      '',
      'Escriba una narrativa de coaching de 3 a 4 oraciones para el líder de ' + scope + ' de ' + unitName + '.',
      '',
      'Estructura:',
      '(1) Celebre una fortaleza visible — mencione un área específica si se destaca.',
      '(2) Identifique la necesidad de crecimiento más común entre las áreas.',
      '(3) Dé una directriz de coaching específica y accionable para usar en el inventario de esta semana.',
      '(4) Termine con una referencia de página de Predicad Mi Evangelio y una escritura que respalde la directriz.',
      '',
      'Reglas:',
      '- NUNCA use la palabra "investigador" — a las personas que están siendo enseñadas siempre se les llama "amigos".',
      '- Escriba en un tono cristiano: alentador, esperanzador y centrado en la fe.',
      '- Edifique al líder — nunca avergüence, culpe ni compare áreas negativamente.',
      '- Fundamente la directriz en los principios del evangelio restaurado y la misión de Jesucristo.',
      '- Puede mencionar áreas por nombre cuando sea útil, pero nunca nombre a misioneros individuales.',
      '- No invente datos. Base cada afirmación en los números anteriores.',
      '- Escriba con naturalidad y claridad, como si hablara con un líder experimentado que ama a los misioneros que dirige.',
      '',
      'Formato (siga exactamente):',
      'Línea 1: El párrafo de coaching (prosa simple, sin viñetas, sin markdown).',
      'Línea 2: PMG p.{número de página} | {referencia de escritura}',
      '',
      'No incluya encabezados, líneas adicionales ni explicaciones más allá de estas dos líneas.',
      '',
      'IMPORTANTE: Escriba su respuesta en español.'
    ].join('\n');

    var response = callGemini(prompt);
    if (!response || !response.trim()) return '';
    _narrativeCache[cacheKey] = response.trim();
    return a1c_renderNarrativeHtml_(response.trim(), C);

  } catch (e) {
    Logger.log('a1c_buildLeadershipNarrative ERROR (' + scope + '/' + unitName + '): ' + e.message);
    return '';
  }
}

// ─── WRITE WEEKLY_BREAKDOWNS ───────────────────────────────────────────────────
/**
 * Reads the mission's active NIGHTLY NUMBER metric keys from QUESTIONS_CONFIG
 * (mirrors CCSM_Agent1A.gs's own a1a_loadCountMetrics — see file header note
 * #5). Read fresh from the sheet each run since GAS re-initializes all
 * top-level state on every execution — Agent1C cannot rely on Agent1A's
 * in-memory A1A_METRICS surviving between chained trigger-fired runs.
 */
function a1c_loadCountMetricKeys() {
  var data = a1c_getSheetData('QUESTIONS_CONFIG');
  if (!data || data.length < 2) return [];
  var h       = data[0].map(function(c) { return String(c).trim(); });
  var keyIdx  = h.indexOf('Metric_Key');
  var actIdx  = h.indexOf('Active');
  var typeIdx = h.indexOf('Data_Type');
  var formIdx = h.indexOf('Form_Type');
  if (keyIdx < 0) return [];
  var keys = [];
  for (var i = 1; i < data.length; i++) {
    if (actIdx  >= 0 && String(data[i][actIdx]  || '').trim().toUpperCase() !== 'TRUE') continue;
    if (typeIdx >= 0 && String(data[i][typeIdx] || '').trim().toUpperCase() !== 'NUMBER') continue;
    if (formIdx >= 0) {
      var formType = String(data[i][formIdx] || '').trim().toUpperCase();
      if (formType !== 'NIGHTLY' && formType !== '') continue;
    }
    var key = String(data[i][keyIdx] || '').trim();
    if (key) keys.push(key);
  }
  return keys;
}

/**
 * Appends one row per area to WEEKLY_BREAKDOWNS for the current week.
 * Skips any area+week combination that already has a row (idempotent
 * re-runs). Header columns are derived dynamically from QUESTIONS_CONFIG's
 * active count metrics + the 5 fixed CCSM rate-metric keys — never Provo's
 * hardcoded English column list (pew, date_metric, gate, renew, nm_ prefixed
 * fields, door-related fields).
 */
function a1c_writeWeeklyBreakdowns(areas, weekEnd) {
  var sheet    = getTab('WEEKLY_BREAKDOWNS');
  var lastRow  = sheet.getLastRow();
  var existing = {};
  var countKeys = a1c_loadCountMetricKeys();

  if (lastRow >= 2) {
    var data    = sheet.getDataRange().getValues();
    var headers = data[0].map(function(h) { return String(h).trim(); });
    var aIdx    = headers.indexOf('area');
    var wIdx    = headers.indexOf('week_end_date');
    if (aIdx >= 0 && wIdx >= 0) {
      for (var i = 1; i < data.length; i++) {
        existing[String(data[i][aIdx]) + '|' + String(data[i][wIdx])] = true;
      }
    }
  }

  if (lastRow === 0) {
    sheet.appendRow(
      ['week_end_date', 'area', 'zone', 'district']
        .concat(countKeys)
        .concat(A1C_RATE_METRIC_KEYS)
        .concat(['strength1_metric', 'strength2_metric', 'growth_metric',
                 'msg_strength1_id', 'msg_strength2_id', 'msg_growth_id', 'submissions'])
    );
  }

  var newRows = [];
  Object.keys(areas).forEach(function(areaName) {
    var key = areaName + '|' + weekEnd;
    if (existing[key]) return;
    var a = areas[areaName];
    var s = a.stats || {};
    var row = [weekEnd, areaName, a.zone || '', a.district || ''];
    countKeys.forEach(function(k) { row.push(s[k] || 0); });
    A1C_RATE_METRIC_KEYS.forEach(function(k) { row.push(Math.round((s[k] || 0) * 1000) / 1000); });
    row.push(
      (a.strength1 && a.strength1.key) || '',
      (a.strength2 && a.strength2.key) || '',
      (a.growth    && a.growth.key)    || '',
      (a.msg_strength1 && a.msg_strength1.messageId) || '',
      (a.msg_strength2 && a.msg_strength2.messageId) || '',
      (a.msg_growth    && a.msg_growth.messageId)    || '',
      s.submissions || 0
    );
    newRows.push(row);
  });

  if (newRows.length > 0) {
    var startRow = sheet.getLastRow() + 1;
    sheet.getRange(startRow, 1, newRows.length, newRows[0].length).setValues(newRows);
  }
}

// ─── FEEDBACK_HISTORY ──────────────────────────────────────────────────────────
/**
 * Records the messages actually assembled into this week's coaching emails
 * via CCSM_Helpers.gs's shared recordMessageSent() — see file header note
 * #4. Only msg_strength1 is recorded under SUNDAY_COACHING_STRENGTH
 * (mirrors Provo's original a1c_writeFeedbackHistory choice: FEEDBACK_HISTORY
 * has one row per area+category, so recording both strength messages would
 * just have the second overwrite the first).
 */
function a1c_recordFeedbackHistory(areas) {
  Object.keys(areas).forEach(function(areaName) {
    var area    = areas[areaName];
    var areaKey = area.code || areaName; // matches CCSM_Agent1B.gs's areaKey formula

    if (area.msg_strength1 && area.msg_strength1.messageId) {
      recordMessageSent(areaKey, area.msg_strength1.messageId, 'SUNDAY_COACHING_STRENGTH');
    }
    if (area.msg_growth && area.msg_growth.messageId) {
      var growthMetric = (area.growth && area.growth.key) || '';
      recordMessageSent(areaKey, area.msg_growth.messageId, 'SUNDAY_COACHING_GROWTH', growthMetric);
    }
  });
}

// ─── UTILITIES ─────────────────────────────────────────────────────────────────
function a1c_getSheetData(tabName) {
  var sheet = getTab(tabName);
  if (!sheet || sheet.getLastRow() === 0) return [];
  return sheet.getDataRange().getValues();
}

function a1c_esc(str) {
  return String(str || '')
    .replace(/&/g,  '&amp;')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;')
    .replace(/"/g,  '&quot;');
}

/**
 * Formats a metric value for display: rate metrics (0..1 ratios) and
 * effort_score (0..3 weighted average) render as percentages; count metrics
 * render as a plain rounded number. Shared by the area detail panel and the
 * Gemini prompt-building area lines.
 */
function a1c_formatMetricValue(key, value) {
  var v = value || 0;
  if (key === 'effort_score') return Math.round(v / 3.0 * 100) + '%';
  if (A1C_RATE_METRIC_KEYS.indexOf(key) >= 0) return Math.round(v * 100) + '%';
  return String(Math.round(v));
}

/**
 * Formats the Predicad Mi Evangelio (Preach My Gospel) reference for
 * display, straight from the MESSAGE_BANK PMG_Chapter/pmgPage value. Never
 * invents a page number — returns '' when the cell is empty.
 */
function a1c_formatPmgRef(raw) {
  var v = String(raw || '').trim();
  if (!v) return '';
  if (/predicad mi evangelio/i.test(v)) return v; // already names the book — verbatim
  v = v.replace(/^pmg\b[\s.,:–—-]*/i, '');         // drop a legacy "PMG" prefix if present
  if (/^\d+$/.test(v)) v = 'p.' + v;               // bare page number → "p.157"
  return 'Predicad Mi Evangelio, ' + v;
}

/**
 * Formats a 'yyyy-MM-dd' date string as "{day} de {mes}" using
 * A1C_SPANISH_MONTHS — see file header note #6 for why Utilities.formatDate's
 * 'MMMM' token is never trusted to localize.
 */
function a1c_formatDate(dateStr) {
  try {
    var p  = dateStr.split('-');
    var d  = new Date(parseInt(p[0], 10), parseInt(p[1], 10) - 1, parseInt(p[2], 10), 12);
    var tz = getMissionTimezone();
    var day   = Utilities.formatDate(d, tz, 'd');
    var month = parseInt(Utilities.formatDate(d, tz, 'M'), 10);
    return day + ' de ' + (A1C_SPANISH_MONTHS[month - 1] || '');
  } catch (e) {
    return dateStr;
  }
}

// ─── BATCH NARRATIVE PRE-GENERATION ───────────────────────────────────────────
/**
 * Renders raw Gemini narrative text into an HTML coaching block. Handles
 * both per-unit format (PMG on its own line) and batch format (PMG inline
 * at end).
 */
function a1c_renderNarrativeHtml_(rawText, C) {
  if (!rawText) return '';
  // Belt-and-suspenders: Gemini should never use "investigador" but filter anyway.
  var text = rawText.trim().replace(/\binvestigadores\b/gi, 'amigos').replace(/\binvestigador\b/gi, 'amigo');
  var pmgLine = '';
  var narrative = text;

  var pmgMatch = text.match(/PMG p\.\d[^\n]*/i);
  if (pmgMatch) {
    pmgLine   = pmgMatch[0].trim();
    narrative = text.replace(pmgMatch[0], '').replace(/[\s|]+$/, '').trim();
  }
  if (!narrative) return '';

  var html = '<div style="background:#f0f4f8;border-left:4px solid ' + C.header +
             ';padding:12px 16px;margin-bottom:14px;border-radius:0 6px 6px 0;">';
  html += '<div style="font-size:12px;font-weight:700;color:' + C.header +
          ';margin-bottom:6px;text-transform:uppercase;letter-spacing:0.05em;">Coaching de Liderazgo</div>';
  html += '<div style="font-size:13px;line-height:1.7;color:#1f2937;">' +
          a1c_esc(narrative) + '</div>';
  if (pmgLine) {
    html += '<div style="margin-top:8px;font-size:11px;color:#6b7280;">📖 ' +
            a1c_esc(pmgLine) + '</div>';
  }
  html += '</div>';
  return html;
}

/**
 * Generates all zone and district narratives using 2 batch Gemini calls (one
 * per scope type). Stores results in _narrativeCache so
 * a1c_buildLeadershipNarrative() skips individual calls. Mission narrative
 * is not pre-generated here — it's generated on first demand and cached.
 */
function a1c_pregenerateNarratives(summaries, areas, weekEnd) {
  var zoneNames = Object.keys(summaries.zones     || {});
  var distNames = Object.keys(summaries.districts || {});

  if (zoneNames.length > 0) {
    var zoneNarratives = a1c_fetchBatchNarratives_('zone', summaries.zones, areas, weekEnd);
    Object.keys(zoneNarratives).forEach(function(name) {
      _narrativeCache['zone:' + name] = zoneNarratives[name];
    });
    Logger.log('Agent1C: narrativas de zona pre-generadas: ' + Object.keys(zoneNarratives).length);
  }

  if (distNames.length > 0) {
    var distNarratives = a1c_fetchBatchNarratives_('district', summaries.districts, areas, weekEnd);
    Object.keys(distNarratives).forEach(function(name) {
      _narrativeCache['district:' + name] = distNarratives[name];
    });
    Logger.log('Agent1C: narrativas de distrito pre-generadas: ' + Object.keys(distNarratives).length);
  }
}

/**
 * Generates coaching narratives for all units of one scope type in a single
 * Gemini call. Returns {unitName: rawNarrativeText}. On any failure returns
 * {} so per-unit fallback fires.
 */
function a1c_fetchBatchNarratives_(scopeType, summaryMap, areas, weekEnd) {
  var unitNames = Object.keys(summaryMap);
  if (unitNames.length === 0) return {};

  var dateLabel = weekEnd ? a1c_formatDate(weekEnd) : 'esta semana';
  var filterKey = scopeType === 'zone' ? 'zone' : 'district';

  var lines = [
    'Eres un asistente de análisis de misión para la ' + getMissionName() + '.',
    'Semana que termina: ' + dateLabel,
    '',
    'Genere una narrativa de coaching para cada ' + scopeType + ' que aparece a continuación.',
    'Devuelva un objeto JSON válido: cada clave es el nombre exacto del ' + scopeType + ',',
    'cada valor es una narrativa (3-4 oraciones, luego: PMG p.{página} | {escritura}).',
    '',
    'REGLAS:',
    '- NUNCA use la palabra "investigador" — a las personas que están siendo enseñadas siempre se les llama "amigos"',
    '- Tono cristiano: alentador, esperanzador, centrado en la fe — nunca avergüence ni compare áreas negativamente',
    '- Mencione áreas específicas por nombre cuando una se destaque — nunca nombre a misioneros individuales',
    '- Note patrones entre áreas (por ejemplo, si la mayoría tiene una tasa de conversaciones significativas baja o poco esfuerzo, dígalo explícitamente)',
    '- Termine cada narrativa con: PMG p.{página} | {referencia de escritura}',
    '- No invente datos — base cada afirmación en los números proporcionados',
    '- Genere SOLO JSON válido — sin bloques de código markdown, sin texto adicional',
    '- IMPORTANTE: Escriba toda su respuesta en español.',
    '',
    scopeType.toUpperCase() + ' — DATOS:'
  ];

  unitNames.forEach(function(unitName) {
    var totals    = summaryMap[unitName] || {};
    var unitAreas = [];
    Object.keys(areas).forEach(function(areaName) {
      if (areas[areaName][filterKey] === unitName) {
        unitAreas.push({
          name:   areaName,
          stats:  areas[areaName].stats  || {},
          growth: areas[areaName].growth || null
        });
      }
    });
    lines.push('');
    lines.push(scopeType + ': ' + unitName);
    lines.push('Reportaron: ' + (totals.submitted || 0) + '/' + (totals.total_areas || 0) +
      ' | Contactos: ' + (totals.contacts_made || 0) +
      ' | Nuevas Personas: ' + (totals.new_people_found || 0) +
      ' | Invitaciones al Bautismo: ' + (totals.baptismal_invitations || 0));
    unitAreas.forEach(function(a) {
      lines.push('  ' + a1c_areaSummaryLine_(a));
    });
  });

  try {
    var response = callGemini(lines.join('\n'), 5000);
    var cleaned  = response.replace(/^```(?:json)?\s*/i, '').replace(/\s*```\s*$/i, '').trim();
    return JSON.parse(cleaned);
  } catch (e) {
    Logger.log('a1c_fetchBatchNarratives_ ERROR (' + scopeType + '): ' + e.message + '. Se usará el respaldo por unidad.');
    return {};
  }
}
