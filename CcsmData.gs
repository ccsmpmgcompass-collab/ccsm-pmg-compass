/**
 * CcsmData.gs — CCSM shared data module
 * ------------------------------------------------------------------
 * Single source of truth for the CCSM (Chile Concepción South Mission) fork
 * of PMG Compass: zone/area map, the daily/weekly metric maps, form
 * structural strings, initial AGENT_CONFIG rows, the MISSION_ORG roster, and
 * the tab-build spec. The sheet builder and the CCSM_* agents both read from
 * these globals — keeping data separate from builder/agent logic means the
 * next mission (#3) only has to swap this one file.
 *
 * Spanish text (headerEs / displayEs) is copied CHARACTER-FOR-CHARACTER from
 * the live ES form builders (DailyReportForm_ES.gs, WeeklyReportForm_ES.gs)
 * so that agents parsing real form responses match on exact string equality.
 * CCSM_ZONES is copied verbatim from WeeklyReportForm.gs (ZONES).
 *
 * Source for MISSION_ORG rows: CurrentOrganization-Excel (3).xls, parsed by
 * tools/emit_mission_org.py (one-off; re-run if the roster changes before
 * go-live). Companion emails are intentionally left blank — filled in later
 * from Church-issued @missionary.org addresses.
 */

// ==================================================================
// ZONES — verbatim copy of WeeklyReportForm.gs:42-53 (`ZONES`). The test
// harness asserts deep equality against the live form builder's data, so
// this must never be hand-edited independently of that file.
// ==================================================================
var CCSM_ZONES = {
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
// NIGHTLY (daily) metric map — one row per question on the nightly form,
// in form order. headerEs is copied verbatim from DailyReportForm_ES.gs
// QUESTIONS[].title (character-for-character, accents/¿ included).
// ==================================================================
var CCSM_NIGHTLY_QUESTIONS = [
  { key: 'report_date',               headerEs: '¿Qué fecha está ingresando?', type: 'DATE',   displayEs: 'Fecha del Informe', order: 1 },
  { key: 'exchanges',                 headerEs: '¿Participó en uno o más intercambios?', type: 'YESNO', displayEs: 'Intercambios', order: 2 },
  { key: 'roleplays',                 headerEs: 'Prácticas de enseñanza realizadas hoy', type: 'NUMBER', displayEs: 'Prácticas de Enseñanza', order: 3 },
  { key: 'contacts_attempted',        headerEs: 'Intentos de contacto con amigos', type: 'NUMBER', displayEs: 'Intentos de Contacto', order: 4 },
  { key: 'contacts_made',             headerEs: 'Contactos con amigos', type: 'NUMBER', displayEs: 'Contactos', order: 5 },
  { key: 'meaningful_conversations',  headerEs: 'Conversaciones significativas con amigos', type: 'NUMBER', displayEs: 'Conversaciones Significativas', order: 6 },
  { key: 'new_people_found',          headerEs: 'Nuevas personas encontradas', type: 'NUMBER', displayEs: 'Nuevas Personas Encontradas', order: 7 },
  { key: 'friend_lessons',            headerEs: 'Lecciones con amigos', type: 'NUMBER', displayEs: 'Lecciones con Amigos', order: 8 },
  { key: 'pmf_lessons',               headerEs: 'Lecciones con familias en las que no todos son miembros', type: 'NUMBER', displayEs: 'Lecciones con Familias Parciales', order: 9 },
  { key: 'rc_lessons',                headerEs: 'Lecciones con conversos recientes', type: 'NUMBER', displayEs: 'Lecciones con Conversos Recientes', order: 10 },
  { key: 'rc_lessons_mcp',            headerEs: 'Lecciones con conversos recientes usando Mi Senda de los Convenios', type: 'NUMBER', displayEs: 'Lecciones con CR (Mi Senda de los Convenios)', order: 11 },
  { key: 'friend_texts',              headerEs: 'Mensajes de texto enviados a amigos', type: 'NUMBER', displayEs: 'Mensajes de Texto a Amigos', order: 12 },
  { key: 'friend_calls',              headerEs: 'Llamadas telefónicas a amigos', type: 'NUMBER', displayEs: 'Llamadas a Amigos', order: 13 },
  { key: 'member_contacts',           headerEs: 'Contactos realizados con miembros del barrio', type: 'NUMBER', displayEs: 'Contactos con Miembros', order: 14 },
  { key: 'lessons_member_present',    headerEs: 'Lecciones con un miembro presente', type: 'NUMBER', displayEs: 'Lecciones con Miembro Presente', order: 15 },
  { key: 'references_asked',          headerEs: 'Referencias solicitadas', type: 'NUMBER', displayEs: 'Referencias Solicitadas', order: 16 },
  { key: 'member_referrals_received', headerEs: 'Referencias de miembros recibidas hoy', type: 'NUMBER', displayEs: 'Referencias de Miembros Recibidas', order: 17 },
  { key: 'bom_shared',                headerEs: 'Copias del Libro de Mormón entregadas', type: 'NUMBER', displayEs: 'Libros de Mormón Entregados', order: 18 },
  { key: 'church_invites',            headerEs: 'Invitaciones a la Iglesia extendidas', type: 'NUMBER', displayEs: 'Invitaciones a la Iglesia', order: 19 },
  { key: 'baptism_doctrine_lessons',  headerEs: 'Lecciones en las que se enseñó la doctrina del bautismo', type: 'NUMBER', displayEs: 'Lecciones de Doctrina del Bautismo', order: 20 },
  { key: 'baptismal_invitations',     headerEs: 'Invitaciones al bautismo extendidas', type: 'NUMBER', displayEs: 'Invitaciones al Bautismo', order: 21 },
  { key: 'baptismal_calendars',       headerEs: 'Calendarios bautismales entregados', type: 'NUMBER', displayEs: 'Calendarios Bautismales Entregados', order: 22 },
  { key: 'effort',                    headerEs: '¿Dio todo, la mayor parte o algo de esfuerzo en el altar del sacrificio hoy?', type: 'CHOICE', displayEs: 'Nivel de Esfuerzo', order: 23 }
];

// ==================================================================
// WEEKLY metric map — 3 intro questions + 7 key-indicator bases, each
// rendered twice (_real / _meta), matching WeeklyReportForm_ES.gs's
// KEY_INDICATORS list and its '<title> (Real)' / '<title> (Meta)' pattern.
// ==================================================================
var CCSM_WEEKLY_QUESTIONS = [
  { key: 'report_date',         headerEs: '¿Qué fecha está ingresando?', type: 'DATE',  displayEs: 'Fecha del Informe Semanal', order: 1 },
  { key: 'leader_call',         headerEs: '¿Recibió una llamada de sus líderes?', type: 'YESNO', displayEs: 'Llamada de Líderes', order: 2 },
  { key: 'correlation_meeting', headerEs: '¿Usted y sus líderes locales realizaron una reunión de coordinación semanal?', type: 'YESNO', displayEs: 'Reunión de Coordinación Semanal', order: 3 },

  { key: 'ki_new_people_real',          headerEs: 'Nuevas personas encontradas (Real)', type: 'NUMBER', displayEs: 'Nuevas Personas Encontradas (Real)', order: 4 },
  { key: 'ki_new_people_meta',          headerEs: 'Nuevas personas encontradas (Meta)', type: 'NUMBER', displayEs: 'Nuevas Personas Encontradas (Meta)', order: 5 },
  { key: 'ki_member_lessons_real',      headerEs: 'Lecciones con miembros (Real)', type: 'NUMBER', displayEs: 'Lecciones con Miembros (Real)', order: 6 },
  { key: 'ki_member_lessons_meta',      headerEs: 'Lecciones con miembros (Meta)', type: 'NUMBER', displayEs: 'Lecciones con Miembros (Meta)', order: 7 },
  { key: 'ki_friends_sacrament_real',   headerEs: 'Amigos en la reunión sacramental (Real)', type: 'NUMBER', displayEs: 'Amigos en la Reunión Sacramental (Real)', order: 8 },
  { key: 'ki_friends_sacrament_meta',   headerEs: 'Amigos en la reunión sacramental (Meta)', type: 'NUMBER', displayEs: 'Amigos en la Reunión Sacramental (Meta)', order: 9 },
  { key: 'ki_friends_first_week_real',  headerEs: 'Amigos en la Iglesia durante su primera semana de enseñanza (Real)', type: 'NUMBER', displayEs: 'Amigos en la Iglesia (Primera Semana) (Real)', order: 10 },
  { key: 'ki_friends_first_week_meta',  headerEs: 'Amigos en la Iglesia durante su primera semana de enseñanza (Meta)', type: 'NUMBER', displayEs: 'Amigos en la Iglesia (Primera Semana) (Meta)', order: 11 },
  { key: 'ki_baptismal_date_real',      headerEs: 'Amigos con fecha bautismal (Real)', type: 'NUMBER', displayEs: 'Amigos con Fecha Bautismal (Real)', order: 12 },
  { key: 'ki_baptismal_date_meta',      headerEs: 'Amigos con fecha bautismal (Meta)', type: 'NUMBER', displayEs: 'Amigos con Fecha Bautismal (Meta)', order: 13 },
  { key: 'ki_baptized_confirmed_real',  headerEs: 'Bautizados y confirmados (Real)', type: 'NUMBER', displayEs: 'Bautizados y Confirmados (Real)', order: 14 },
  { key: 'ki_baptized_confirmed_meta',  headerEs: 'Bautizados y confirmados (Meta)', type: 'NUMBER', displayEs: 'Bautizados y Confirmados (Meta)', order: 15 },
  { key: 'ki_rc_at_church_real',        headerEs: 'Conversos recientes en la Iglesia (Real)', type: 'NUMBER', displayEs: 'Conversos Recientes en la Iglesia (Real)', order: 16 },
  { key: 'ki_rc_at_church_meta',        headerEs: 'Conversos recientes en la Iglesia (Meta)', type: 'NUMBER', displayEs: 'Conversos Recientes en la Iglesia (Meta)', order: 17 }
];

// ==================================================================
// Structural (non-metric) form strings shared by both forms.
// ==================================================================
var CCSM_FORM_STRUCTURAL = {
  zoneCol: '¿En qué zona sirve?',
  areaCol: '¿En qué área sirve?',
  dateCol: '¿Qué fecha está ingresando?',
  effortChoices: ['Todo', 'La mayor parte', 'Algo']
};

// ==================================================================
// AGENT_CONFIG initial rows — base table per
// docs/superpowers/specs/2026-07-11-ccsm-sheet-and-agents-design.md, plus
// the rate-target keys and per-metric GOAL_<key> rows required by the
// ported Agent2/AgentScores logic (Agent2 reads GOAL_{key} for each numeric
// daily metric; blank until the user/GOALS_CONFIG populates them).
// ==================================================================
var CCSM_AGENT_CONFIG_ROWS = [
  ['MISSION_NAME', 'Chile Concepción South Mission'],
  ['MISSION_LANGUAGE', 'ES'],
  ['MISSION_TIMEZONE', 'America/Santiago'],
  ['MISSION_LOCALE', 'es_CL'],
  ['TEST_MODE', 'TRUE'],
  ['TEST_INBOX_EMAIL', 'CCSM.PMG.Compass@gmail.com'],
  ['SEND_FROM_EMAIL', 'CCSM.PMG.Compass@gmail.com'],
  ['SYSTEM_START_DATE', ''],
  ['NIGHTLY_FORM_LINK', ''],
  ['WEEKLY_FORM_LINK', ''],
  ['RELAY_1_URL', ''],
  ['RELAY_2_URL', ''],
  ['RELAY_SECRET', ''],
  ['GEMINI_QA_MODEL', 'gemini-2.5-flash'],
  ['MISSED_DAYS_LOOKBACK', '3'],
  // Which agent owns weekly-form non-submitter reminders. AgentReminder's
  // ar_checkWeeklyCompliance() and AgentEscalation's System 2 both email
  // non-submitting companionships about the weekly form, with the SAME
  // Spanish subject — running both double-nags every companionship. Exactly
  // one owner is active at a time. See CCSM_Setup.gs's file header for the
  // full deployment decision and why AGENT_ESCALATION is the shipped default.
  // 'AGENT_ESCALATION' (default) | 'AGENT_REMINDER' | 'BOTH' (disables the gate).
  ['WEEKLY_REMINDER_OWNER', 'AGENT_ESCALATION'],
  ['CONTACT_RATE_TARGET', '0.50'],
  ['MC_RATE_TARGET', '0.50'],
  ['LESSON_RATE_TARGET', '0.20'],
  ['CLOSE_RATE_TARGET', '0.25'],
  ['EFFORT_SCORE_TARGET', '2.75'],
  ['TRANSFER_START_DATE', ''],
  ['GOAL_roleplays', ''],
  ['GOAL_contacts_attempted', ''],
  ['GOAL_contacts_made', ''],
  ['GOAL_meaningful_conversations', ''],
  ['GOAL_new_people_found', ''],
  ['GOAL_friend_lessons', ''],
  ['GOAL_pmf_lessons', ''],
  ['GOAL_rc_lessons', ''],
  ['GOAL_rc_lessons_mcp', ''],
  ['GOAL_friend_texts', ''],
  ['GOAL_friend_calls', ''],
  ['GOAL_member_contacts', ''],
  ['GOAL_lessons_member_present', ''],
  ['GOAL_references_asked', ''],
  ['GOAL_member_referrals_received', ''],
  ['GOAL_bom_shared', ''],
  ['GOAL_church_invites', ''],
  ['GOAL_baptism_doctrine_lessons', ''],
  ['GOAL_baptismal_invitations', ''],
  ['GOAL_baptismal_calendars', '']
];

// ==================================================================
// MISSION_ORG — headers verified against every forked agent's accessors
// (Agent1C.gs row['Is_AP'], Agent3.gs/AgentReminder.gs Companion1_Email
// etc.; see task-2 report for the full grep reconciliation). Rows are
// generated by tools/emit_mission_org.py from the IMOS CurrentOrganization
// export; Companion emails are intentionally blank (filled in later).
// ==================================================================
var CCSM_MISSION_ORG_HEADERS = ['Area_Code','Area_Name','Zone','District','Companion1_Name','Companion1_Email',
   'Companion2_Name','Companion2_Email','Is_DL','Is_ZL','Is_STL','Is_AP','Is_MP','Active'];

var CCSM_MISSION_ORG_ROWS = [
 ["A001", "Alemania 2", "Angol", "Alemania 2", "Rees, Nicolas Clay", "", "Tanea, Evander Isopo", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A002", "Collipulli", "Angol", "Alemania 2", "Andrade, Bruno Bilar", "", "Wright, Caiden Paul", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A003", "Los Sauces", "Angol", "Alemania 2", "Tiul Poou, Bitner Oswaldo", "", "Coombs, Mark Emerson", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A004", "Tijeral y Renaico", "Angol", "Alemania 2", "Villalba, Lucia Abril", "", "Kolste, Savannah Mattie", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A005", "Alemania 1", "Angol", "Los Confines", "Borup, Carson Reed", "", "McKea, Matthew John", "", "FALSE", "TRUE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A006", "El Mirador", "Angol", "Los Confines", "Moessing, Peter Stewart", "", "Flores, Jeander Jesús", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A007", "Huequen", "Angol", "Los Confines", "Grippo, Laura Caterina", "", "Aguilar Hinojosa, Angelica Celeste", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A008", "Los Confines", "Angol", "Los Confines", "Mostajo, Sebastián Mahonry", "", "dos Santos Ribeiro, Gustavo ", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A009", "Cañete 1", "Arauco", "Cañete 2", "Lazenby, Dutch Clay", "", "Tuckfield, Nathan Christopher", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A010", "Cañete 2", "Arauco", "Cañete 2", "Park, James Russell", "", "Bartlett, Keanan Daniel", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A011", "Lebu 1", "Arauco", "Cañete 2", "Leach, Caroline Elizabeth", "", "Sullivan, Amanda Elaine", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A012", "Lebu 2", "Arauco", "Cañete 2", "Altamira, Morena Camila", "", "Fielding, Melody Reese", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A013", "Los Alamos", "Arauco", "Cañete 2", "Walker, Kyson Holmes", "", "Lewis, Drake Mcclintock", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A014", "Arauco 1", "Arauco", "Curanilahue 1", "Prendergast, Mark Norman", "", "Pilkington, Michael ", "", "FALSE", "TRUE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A015", "Arauco 2", "Arauco", "Curanilahue 1", "Villegas, Lucas Darian", "", "James, Luke Robert", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A016", "Curanilahue 1", "Arauco", "Curanilahue 1", "Evans, Kimball Jacob", "", "Gonzalez, Leonel Francisco", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A017", "Curanilahue 2", "Arauco", "Curanilahue 1", "Rigg, River Charles", "", "Peterson, Cameron Chad", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A018", "Camilo Olivarria 1", "Camilo", "Camilo 1", "Osborne, Easton Barton", "", "Woodward, William Farley", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A019", "Camilo Olivarria 2", "Camilo", "Camilo 1", "Ruiz, Luis Humberto", "", "Adasme, Said Zamir Manuel", "", "FALSE", "TRUE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A020", "Lagunillas 1", "Camilo", "Camilo 1", "Pedersen, Remington Sadie", "", "Reintl, Xiomara Dalila", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A021", "Lota 2", "Camilo", "Camilo 1", "Province, William Jackson", "", "Garcia, Douglas Diogo Isper Guedes", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A022", "Camilo Olivarria 3", "Camilo", "Lota 1", "Kunzler, Jason William", "", "McPhie, Adam David", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A023", "Coronel", "Camilo", "Lota 1", "Richards, Mark Allan", "", "Kimball, Parker Smith", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A024", "Lagunillas 2", "Camilo", "Lota 1", "Torgerson, Hailee Emma", "", "Malan, Grace Bailey", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A025", "Lota 1", "Camilo", "Lota 1", "Flake, Tyler Reed", "", "Sánchez Padilla, Louis Taylor", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A026", "Cabrero 1", "Los Angeles Norte", "Cabrero 2", "Anderson, Collin Eric", "", "Escalante Wills, Ismael ", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A027", "Cabrero 2", "Los Angeles Norte", "Cabrero 2", "Johnson, Graham Dyer", "", "Po'uha, Aiden Elone", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A028", "Yumbel", "Los Angeles Norte", "Cabrero 2", "Romero Hernández, Hannah Paola", "", "Espejo, Amparo Belen", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A029", "Galvarino 2", "Los Angeles Norte", "Laja 1", "Rodriguez, Samuel Caleb", "", "Riquelme, Enzo David", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A030", "Huepil & Tucapel & Villa Obispo", "Los Angeles Norte", "Laja 1", "Payne, Marcus Jay", "", "Arens Rodas, Aarón Eduardo", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A031", "Laja 1", "Los Angeles Norte", "Laja 1", "West, Seth Angus", "", "Segovia, Ulises Román", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A032", "Villa O'Higgins", "Los Angeles Norte", "Laja 1", "Foster, Joshua Todd", "", "Condie, Logan Robert", "", "FALSE", "TRUE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A033", "Almirante Latorre", "Los Angeles Norte", "Laja 2", "Bravo, Milagros Solange", "", "Wilson, Grace Ann", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A034", "Galvarino", "Los Angeles Norte", "Laja 2", "Hardy, Russell Raymond", "", "Rondina, Samuel Thomas", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A035", "Laja 2", "Los Angeles Norte", "Laja 2", "Christensen, Landon Scott", "", "Jack, Darren Eber", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A036", "Villa Obispo", "Los Angeles Norte", "Laja 2", "Clawson, Kayla ", "", "Liljenquist, Claire Mary", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A037", "Av. Alemania", "Los Angeles Sur", "Nacimiento 2", "Moncada, Danae Sofía", "", "Turcios Meza, Lindsey Doneth", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A038", "Nacimiento 2", "Los Angeles Sur", "Nacimiento 2", "Wride, Samuel Matthew", "", "Martinez Morales, David Daniel", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A039", "Villa las Americas 2", "Los Angeles Sur", "Nacimiento 2", "Egbers, Presley James", "", "Clifford, Andrew Chad", "", "FALSE", "TRUE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A040", "Nacimiento 1", "Los Angeles Sur", "Villa Esmeralda", "Davis, Ethan Taylor", "", "Bair, Kevin Jacob", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A041", "San Martin 2", "Los Angeles Sur", "Villa Esmeralda", "Bowden, Evelyn ", "", "Brasfield, Addison Makay", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A042", "Santa Barbara", "Los Angeles Sur", "Villa Esmeralda", "Emerson, Naomi Anne", "", "González, Ana Paula", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A043", "Villa Esmeralda", "Los Angeles Sur", "Villa Esmeralda", "Kearns, John Davis", "", "Viegas, Tomas ", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A044", "Mulchen 1", "Los Angeles Sur", "Villa Las Américas 1", "Paré, Delfina Victoria", "", "Alava Pinargote, Jeny Damary", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A045", "Mulchen 2", "Los Angeles Sur", "Villa Las Américas 1", "Rampton, Eliza Jane", "", "Watkins, Sadie Jan", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A046", "San Martín 1", "Los Angeles Sur", "Villa Las Américas 1", "Alonso, Diana Josefa", "", "Rearte, Sofia Antonela", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A047", "Villa Las Americas 1", "Los Angeles Sur", "Villa Las Américas 1", "Okerlund, Cannon Tyler", "", "Collings, Brennon Cael", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A048", "Boca de la Costa 2", "San Pedro", "Lomas Coloradas 2", "Sasser, Jacob Lohk", "", "Dunn, Nathan Cassidy / Wilde, Cole Richard / Olguin, Thomas Gabriel", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A049", "La Marina 1", "San Pedro", "Lomas Coloradas 2", "Turner, Hyrum Patrick", "", "England, Beckham Richard / Inglet, Logan Clark / Stevenson, Cole Nathan", "", "FALSE", "FALSE", "FALSE", "TRUE", "FALSE", "TRUE"],
 ["A050", "Lomas Coloradas 2", "San Pedro", "Lomas Coloradas 2", "Yetter, Rhett Richard", "", "Earl, Ky Wilde / Christensen, Spencer Tyler", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A051", "Boca de la Costa 1", "San Pedro", "Los Huertos", "Phillips, Anderson Dean", "", "Monroe, Jackson Wood", "", "FALSE", "TRUE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A052", "Bosque Mar 2", "San Pedro", "Los Huertos", "Edgren, Sammie Lou", "", "Judd, Kelli Anne", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A053", "Los Huertos", "San Pedro", "Los Huertos", "Harding, Zachary Scott", "", "Low, Corben Jeffrey / Laiton, Carlos Manuel / Caetano, Gustavo Alves / Butterfield, Zackary Barry", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A054", "Oficina 1", "San Pedro", "Los Huertos", "Gillispie, Susan Maria", "", "", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A055", "San Pedro 2", "San Pedro", "Los Huertos", "Spanbauer, Weldon Troy", "", "Higbee, Maxwell Wade", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A056", "Bosque Mar 1", "San Pedro", "Santa Juana", "Richards, Macy Jane", "", "Rosander, Molly Victoria", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A057", "Lomas Coloradas 1", "San Pedro", "Santa Juana", "Aydelotte, Aaron Michael", "", "Sanguineti, Enzo Stefano", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A058", "San Pedro", "San Pedro", "Santa Juana", "Mansilla, Eneas ", "", "Shea, Bracken Michael", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A059", "Santa Juana", "San Pedro", "Santa Juana", "Olivera, Yohan Emanuel", "", "Silva, Gustavo Gabriel", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A060", "Carahue", "Temuco Cautín", "Carahue", "Simmons, Trevor Michael", "", "da Silva Nicácio, Felipe ", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A061", "Cautin 2", "Temuco Cautín", "Carahue", "Haner, Wyatt Scott", "", "Glenn, Daniel Curtis", "", "FALSE", "TRUE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A062", "Llaima 2", "Temuco Cautín", "Carahue", "Linton, Kenzie Myreel", "", "Keller, Katie Anne", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A063", "Cautín 1", "Temuco Cautín", "Cautín 1", "Jimenez, Benny Abdula", "", "Gottems, Arthur Henrique", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A064", "Cunco", "Temuco Cautín", "Cautín 1", "Caballero Ramirez, Mariana Asenath", "", "Lazaro Delgado, Emily Darla", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A065", "Labranza 2", "Temuco Cautín", "Cautín 1", "Andrewsen, Abigail Elizabeth", "", "Zegarra, Sofia Andrea", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A066", "Maquehue 1", "Temuco Cautín", "Cautín 1", "Trauntvein, Olivia Ann", "", "Whitaker, Sally Jean", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A067", "Labranza 1", "Temuco Cautín", "Nueva Imperial", "Weeks, Kya Kanani", "", "Ferreira, Denise ", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A068", "Llaima 1", "Temuco Cautín", "Nueva Imperial", "Murie, Isabella ", "", "Evans, Rebekah Ann", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A069", "Maquehue 2", "Temuco Cautín", "Nueva Imperial", "Adams, Kayli Geniel", "", "Hansen, Mazie Jolene", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A070", "Nueva Imperial", "Temuco Cautín", "Nueva Imperial", "Cabrera, Juan Gabriel", "", "Vacaflores, Widen Moroni", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A071", "Catrihuala 2", "Temuco Ñielol", "Lautaro 1", "da Silva, Rafael Zarza", "", "Catten, Evan Marco", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A072", "Lautaro 1", "Temuco Ñielol", "Lautaro 1", "Hadley, Luke Dale", "", "Huskinson, Ethan Gregory", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A073", "Lican Ray 2", "Temuco Ñielol", "Lautaro 1", "Berrú, Nicole Anghely", "", "Dominguez, Naira Tamara", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A074", "Vilcun", "Temuco Ñielol", "Lautaro 1", "Kofe, Rimoni ", "", "Christensen, Caleb Dustin", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A075", "Catrihuala 1", "Temuco Ñielol", "Lautaro 2", "Miller, Conner Monroe", "", "Jensen, Micah Rudger", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A076", "Lautaro 2", "Temuco Ñielol", "Lautaro 2", "Poulsen, Bryce MacGregor", "", "Gutierrez, Jose Gonzalo", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A077", "Lican Ray 1", "Temuco Ñielol", "Lautaro 2", "Hazar, Cali Christine", "", "Wood, Annika Elaine", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A078", "Ñielol 2", "Temuco Ñielol", "Lautaro 2", "Mineer, Megan Emma", "", "Recksiek, Rebekah Ann", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A079", "Caupolicán 1", "Temuco Ñielol", "Quirihue 1", "May, Lauren ", "", "Sweeten, McKayla Anne", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A080", "Quirihue 1", "Temuco Ñielol", "Quirihue 1", "Escribar, Francisco Antonio Enrique", "", "Pincock, Lincoln Aaron", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A081", "Quirihue 2", "Temuco Ñielol", "Quirihue 1", "Corry, Tyler Glen", "", "Soto, Santiago Javier", "", "FALSE", "TRUE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A082", "Ñielol 1", "Temuco Ñielol", "Quirihue 1", "Turner, Joshua Russell", "", "Madoery, Tomas Alessandro", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A083", "Curacautín", "Victoria", "Curacautín", "Tenny, Benjamin Pierce", "", "Evans, Nathan Bradley", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A084", "Perquenco", "Victoria", "Curacautín", "Ravelo, Fernanda Antonia", "", "Meza Huallpa, Victoria Abish Kimberly", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A085", "Traiguen 1", "Victoria", "Curacautín", "Larson, Everett Robert", "", "Acosta, Mateo David", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A086", "Tolhuaca", "Victoria", "Traiguen 2", "Hart, Evan Harry", "", "Langford, Jaxon Thomas", "", "FALSE", "TRUE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A087", "Traiguen 2", "Victoria", "Traiguen 2", "Ruvalcaba, Knell Eduardo", "", "Cabrera, Curt Antonio", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A088", "Victoria 1", "Victoria", "Traiguen 2", "Pascual, Jasmin Raquel", "", "Knaphus, Jessie Reese", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A089", "Victoria 2", "Victoria", "Traiguen 2", "Smith, Allie Kate", "", "Harper, Sydney Anne", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A090", "Freire", "Villarrica", "Pitrufquen 2", "Calizaya, Eva Mayarra", "", "Mendieta Fonseca, Melany Sariah", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A091", "Pitrufquen 1", "Villarrica", "Pitrufquen 2", "Johnson, Benjamin Sidney", "", "Young, Matthew Douglas", "", "FALSE", "TRUE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A092", "Pitrufquen 2", "Villarrica", "Pitrufquen 2", "Berroa, Donato Mateo", "", "de Farias, Nadson Silva", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A093", "Loncoche", "Villarrica", "Pucón 1", "Seamons, Sarah Elaine", "", "Clark, Rachel Olive", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A094", "Pucón 1", "Villarrica", "Pucón 1", "Andersen, Tyler Clayton", "", "Heath, Bryson Lance", "", "TRUE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A095", "Volcán 2", "Villarrica", "Pucón 1", "Anfuso, Melina Ailin", "", "Sylvester, Ally Lin", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A096", "Ancahual", "Villarrica", "Volcán 1", "Cabrera, Leidy Nohemi", "", "Cisneros, Maria de los Angeles", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A097", "MLS Pucón", "Villarrica", "Volcán 1", "Bright, Susan Lynn", "", "Bright, Leslie Hobert", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"],
 ["A098", "Pucón 2", "Villarrica", "Volcán 1", "Lagraña, Melina Lucila", "", "Rocha Ruiz, Jackeling Gabriela", "", "FALSE", "FALSE", "TRUE", "FALSE", "FALSE", "TRUE"],
 ["A099", "Volcán 1", "Villarrica", "Volcán 1", "Allred, Tyler Joseph", "", "Estrada Ortiz, Mario Daniel", "", "FALSE", "FALSE", "FALSE", "FALSE", "FALSE", "TRUE"]
];

// ==================================================================
// TAB_SPECS — one entry per sheet tab the builder creates. `headers: null`
// means the tab is created empty and a ported agent writes its own header
// row on first run (e.g. a3_updateDailyLog). Where an agent requires
// pre-existing headers, this list matches that agent's indexOf('...')
// calls exactly (verified against the Provo docs/*.gs sources).
//
// Corrections made here vs. the original design-doc sketch, after grepping
// the real Provo accessors (see task-2 report for detail — several header
// lists in the design spec did not match the code they're meant to drive):
//   - MESSAGE_BANK:      'PMG_Page' -> 'PMG_Chapter' (Helpers.gs col_(),
//     Agent1C.gs/Agent6.gs all read 'PMG_Chapter'; 'PMG_Page' only appears
//     in a stale one-off migration script, not any live accessor).
//   - KNOWLEDGE_BASE:    real schema (AgentQA.gs setupKnowledgeBase(),
//     aqa_loadKnowledgeBase() — positional row[0..7]) is
//     ID | Category | Question | Answer | Keywords | Source | DateAdded | UseCount,
//     not Entry_ID/Question_Pattern/Answer_Text/Language/Added_By/Active.
//   - FEEDBACK_HISTORY:  real schema (Agent1C.gs a1c_writeFeedbackHistory(),
//     Helpers.gs col_() calls) is
//     Area_ID | Area_Name | Category | Last_Message_ID | Last_Sent_Date |
//     Previous_Message_ID | Previous_Sent_Date | Last_Growth_Metric —
//     not Area_Code/Last_Message_IDs(plural)/missing Category+Previous_*.
//   - AGENT_RUN_LOG:     Helpers.gs logRun() appends POSITIONALLY as
//     [Timestamp, Agent, Status, durationMs/1000 (seconds, rounded),
//     recordsProcessed, emailsSent, error, notes] — header order must match
//     that exact column order or values land under the wrong header.
//   - TRANSFER_SCHEDULE: real schema (AgentTransfer.gs setup + Agent2.gs
//     a2_loadRealTransferHistory_(), which requires 'Start_Date' and
//     'Status' columns) is Transfer_Number | Start_Date | Weeks | Status —
//     there is no End_Date/Type column anywhere in the ported code.
//   - GOALS_CONFIG:      Agent2.gs a2_loadAreaGoals() expects a WIDE table
//     (one column literally named 'Area', then one column PER METRIC KEY
//     holding that area's goal value) — not a long Area_Code/Area_Name/
//     Metric_Key/Goal_Value table. A missing/legacy header is a documented
//     safe no-op in the code ("legacy header / not yet migrated"), so this
//     is left `headers: null` (created empty) rather than guessing a fixed
//     column list; whoever builds GOALS_CONFIG population should use
//     ['Area'].concat(CCSM_NIGHTLY_QUESTIONS NUMBER keys) as the wide header.
// ==================================================================
var CCSM_TAB_SPECS = [
  // {name, headers: [..] or null (empty tab — agent writes its own), prefillVar: name of data var or null}
  { name: 'MISSION_ORG',       headers: CCSM_MISSION_ORG_HEADERS, prefill: 'CCSM_MISSION_ORG_ROWS' },
  { name: 'AGENT_CONFIG',      headers: ['Key', 'Value'],         prefill: 'CCSM_AGENT_CONFIG_ROWS' },
  { name: 'QUESTIONS_CONFIG',  headers: ['Question_ID','Form_Type','Form_Column_Header','Metric_Key','Metric_Display_Name','Data_Type','Include_In_Daily_Log','Include_In_Live_Snapshot','Include_In_Weekly_Breakdown','Display_Order','Active'], prefill: 'derived' },
  { name: 'GOALS_CONFIG',      headers: null, prefill: null },   // real schema is wide (Area + one col/metric); see note above
  { name: 'SCORE_CONFIG',      headers: null, prefill: null },   // seeded by CCSM_AgentScores setup fn (Task 12)
  { name: 'MESSAGE_BANK',      headers: ['Message_ID','Category','Metric','Subcategory','Subject_Line','Body_Text','PMG_Chapter','PMG_Description','Scripture','Scripture_Text','Active'], prefill: null }, // content in Task 13
  { name: 'KNOWLEDGE_BASE',    headers: ['ID','Category','Question','Answer','Keywords','Source','DateAdded','UseCount'], prefill: null },
  { name: 'TRANSFER_SCHEDULE', headers: ['Transfer_Number','Start_Date','Weeks','Status'], prefill: null },
  { name: 'DAILY_LOG',         headers: null, prefill: null },
  { name: 'LIVE_SNAPSHOT',     headers: null, prefill: null },
  { name: 'WEEKLY_KI',         headers: null, prefill: null },
  { name: 'DASHBOARD_SUMMARY', headers: null, prefill: null },
  { name: 'WEEKLY_BREAKDOWNS', headers: null, prefill: null },
  { name: 'SCORES',            headers: null, prefill: null },
  { name: 'GOAL_RECALIBRATION',headers: null, prefill: null },
  { name: 'AGENT_RUN_LOG',     headers: ['Timestamp','Agent','Status','Duration_Sec','Records_Processed','Emails_Sent','Error','Notes'], prefill: null },
  { name: 'AUDIT_LOG',         headers: null, prefill: null },
  { name: 'MISSING_LOG',       headers: null, prefill: null },
  { name: 'FEEDBACK_HISTORY',  headers: ['Area_ID','Area_Name','Category','Last_Message_ID','Last_Sent_Date','Previous_Message_ID','Previous_Sent_Date','Last_Growth_Metric'], prefill: null },
  { name: 'ENCOURAGEMENT_HISTORY', headers: null, prefill: null },
  { name: 'SUGGESTIONS',       headers: null, prefill: null },
  { name: 'SUGGESTIONS_REVIEW',headers: null, prefill: null },
  { name: 'NOTES',             headers: ['Note_ID','Area_Code','Area_Name','Author_Email','Note_Text','Created_At','Reminder_DateTime','Reminder_Sent','Resolved','Resolved_At'], prefill: null }
];
