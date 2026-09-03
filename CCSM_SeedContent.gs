/**
 * CCSM_SeedContent.gs — Spanish MESSAGE_BANK + KNOWLEDGE_BASE seed content
 * ---------------------------------------------------------------------------
 * Forked in structure (batching, "safe to re-run", header-order contract) from
 * Provo's populateMessageBankStructure.gs:1-24 and :247-300 — but NONE of the
 * Provo content is carried over. Provo's file writes 199 English PLACEHOLDER
 * rows for a mission president to fill in by hand; this file writes the real,
 * finished Spanish text for CCSM.
 *
 * WHY THIS FILE MATTERS: message selection across every CCSM agent is
 * pick-not-generate (CCSM_Helpers.gs pickMessage(), CCSM_Agent5B.gs
 * a5b_pickMessage(), CCSM_Agent3.gs a3_loadMissedDayMessages()). Missionary-
 * facing text is NEVER AI-generated. What is in this file is therefore the
 * ENTIRE vocabulary the system can speak to a missionary.
 *
 * ── RUN ONCE (zero-argument, so the Apps Script Run button can call them) ───
 *   seedCcsmMessageBank()    — 193 rows
 *   seedCcsmKnowledgeBase()  — 10 rows
 * Each rewrites its tab from scratch (header + rows), so a run can never
 * duplicate content. ⚠️ seedCcsmMessageBank() is nonetheless INITIAL-SETUP
 * ONLY, not routinely re-runnable: MESSAGE_BANK is mission-editable directly
 * in the sheet (same as LEADERSHIP_MESSAGE_BANK — see CCSM_SeedContent.gs's
 * seedCcsmLeadershipMessageBank()), and re-running would wipe any hand edits.
 * seedCcsmKnowledgeBase() has no such editing workflow and stays safe to
 * re-run any time its content changes in code.
 *
 * ── CONTENT MATRIX (193 MESSAGE_BANK rows) ─────────────────────────────────
 *   SUNDAY_COACHING_STRENGTH  25 metrics x 3 =  75
 *   SUNDAY_COACHING_GROWTH    25 metrics x 3 =  75
 *   FRIDAY_ENCOURAGEMENT      20 metrics x 2 =  40
 *   MISSED_DAYS                              =   3
 *                                              ---
 *                                              193
 * "25 metrics" = the 5 rate metrics of A1A_RATE_METRICS (CCSM_Agent1A.gs)
 * plus the 20 NUMBER-typed nightly metrics of CCSM_NIGHTLY_QUESTIONS
 * (CcsmData.gs). FRIDAY_ENCOURAGEMENT covers only the 20 count metrics —
 * CCSM_Agent5B.gs measures progress against weekly COUNT goals, and rate
 * metrics have no count goal to nudge toward. Category strings were read out
 * of the agents themselves (CCSM_Agent1B.gs:70-80, CCSM_Agent5B.gs:265,
 * CCSM_Agent3.gs:1005) and cross-checked against CCSM_Agent4.gs:94-97.
 *
 * ── THREE CONTENT RULES ENFORCED THROUGHOUT ────────────────────────────────
 * 1. Scripture_Text is BLANK on every row except the two supplied verbatim by
 *    the task brief. Quoting the Spanish LDS edition from memory risks putting
 *    invented scripture in front of missionaries; a blank cell is correct,
 *    a plausible paraphrase is not. CONTENT_REVIEW.md lists the 20 distinct
 *    references so a reviewer can paste the real wording in one pass.
 * 2. NO Predicad Mi Evangelio PAGE numbers. The Spanish edition paginates
 *    differently from the English one, so Provo's page values would be wrong
 *    here. PMG_Chapter carries a chapter-level reference ('Capítulo 9') and
 *    PMG_Description is our own one-line topic summary, not a quoted title.
 *    (Exception: the two brief-supplied rows, kept character-for-character.)
 * 3. No invented statistics, no promises of specific outcomes, no guilt.
 *    Usted/ustedes form throughout — a message is addressed to a companionship.
 */

// =============================================================================
// METRIC META — one entry per coaching metric.
//   slug      : the Message_ID fragment (A-Z0-9 only)
//   chapter   : Predicad Mi Evangelio chapter reference (never a page number)
//   pmgDesc   : our own one-line topic summary (not a quoted chapter title)
//   scripture : Spanish LDS reference. Scripture_TEXT stays blank — see rule 1.
// Keys must match A1A_RATE_METRICS (CCSM_Agent1A.gs:50-65) and the NUMBER
// entries of CCSM_NIGHTLY_QUESTIONS (CcsmData.gs:45-69) exactly; csc_buildRows_
// asserts this at run time so a renamed metric fails loudly instead of
// silently leaving an area with no message.
// =============================================================================
var CSC_METRIC_META = {
  // --- rate metrics (Agent1A A1A_RATE_METRICS) ---
  contact_rate:              { slug: 'CONTACTRATE',   chapter: 'Capítulo 9',  pmgDesc: 'Hallar personas a quienes enseñar',                    scripture: 'D. y C. 4:4-5' },
  mc_rate:                   { slug: 'MCRATE',        chapter: 'Capítulo 10', pmgDesc: 'Conversar y escuchar con verdadera intención',         scripture: 'D. y C. 11:21' },
  lesson_rate:               { slug: 'LESSONRATE',    chapter: 'Capítulo 10', pmgDesc: 'Del primer contacto a la primera lección',             scripture: 'Alma 26:22' },
  close_rate:                { slug: 'CLOSERATE',     chapter: 'Capítulo 11', pmgDesc: 'Invitar a hacer y guardar convenios',                  scripture: 'Moroni 10:4' },
  effort_score:              { slug: 'EFFORT',        chapter: 'Capítulo 6',  pmgDesc: 'Desarrollar los atributos de Cristo',                  scripture: 'D. y C. 4:2' },
  // --- count metrics (nightly NUMBER questions) ---
  roleplays:                 { slug: 'ROLEPLAYS',     chapter: 'Capítulo 10', pmgDesc: 'Practicar la enseñanza con su compañero',              scripture: 'D. y C. 84:85' },
  contacts_attempted:        { slug: 'CONTACTS',      chapter: 'Capítulo 9',  pmgDesc: 'Hablar con todas las personas',                        scripture: 'D. y C. 33:8-10' },
  contacts_made:             { slug: 'CONTACTSMADE',  chapter: 'Capítulo 9',  pmgDesc: 'Acercarse con calidez y sinceridad',                   scripture: 'D. y C. 18:15' },
  meaningful_conversations:  { slug: 'MC',            chapter: 'Capítulo 10', pmgDesc: 'Llevar la conversación a lo que de verdad importa',    scripture: 'D. y C. 11:21' },
  new_people_found:          { slug: 'NEWPEOPLE',     chapter: 'Capítulo 9',  pmgDesc: 'Hallar nuevas personas a quienes enseñar',             scripture: 'Alma 26:22' },
  friend_lessons:            { slug: 'LESSONS',       chapter: 'Capítulo 10', pmgDesc: 'Enseñar a los amigos de la Iglesia',                   scripture: 'D. y C. 42:14' },
  pmf_lessons:               { slug: 'PMF',           chapter: 'Capítulo 13', pmgDesc: 'Enseñar a familias en las que no todos son miembros',  scripture: '3 Nefi 18:21' },
  rc_lessons:                { slug: 'RC',            chapter: 'Capítulo 12', pmgDesc: 'Fortalecer a los conversos recientes',                 scripture: 'Moroni 6:4' },
  rc_lessons_mcp:            { slug: 'RCMCP',         chapter: 'Capítulo 12', pmgDesc: 'Enseñar con Mi Senda de los Convenios',                scripture: 'Moroni 6:4' },
  friend_texts:              { slug: 'TEXTS',         chapter: 'Capítulo 9',  pmgDesc: 'Dar seguimiento por mensaje de texto',                 scripture: 'D. y C. 64:33' },
  friend_calls:              { slug: 'CALLS',         chapter: 'Capítulo 9',  pmgDesc: 'Dar seguimiento por llamada telefónica',               scripture: 'D. y C. 64:33' },
  member_contacts:           { slug: 'MEMBERS',       chapter: 'Capítulo 13', pmgDesc: 'Trabajar de la mano con los miembros del barrio',      scripture: 'Mosíah 18:21' },
  lessons_member_present:    { slug: 'MEMBERPRESENT', chapter: 'Capítulo 13', pmgDesc: 'Enseñar con un miembro presente',                      scripture: 'D. y C. 6:32' },
  references_asked:          { slug: 'REFASKED',      chapter: 'Capítulo 9',  pmgDesc: 'Pedir referencias en cada visita',                     scripture: 'D. y C. 88:81' },
  member_referrals_received: { slug: 'REFRECEIVED',   chapter: 'Capítulo 13', pmgDesc: 'Recibir y atender las referencias de los miembros',    scripture: 'D. y C. 88:81' },
  bom_shared:                { slug: 'BOM',           chapter: 'Capítulo 5',  pmgDesc: 'La función del Libro de Mormón',                       scripture: 'Moroni 10:3-5' },
  church_invites:            { slug: 'CHURCH',        chapter: 'Capítulo 11', pmgDesc: 'Invitar a asistir a la Iglesia',                       scripture: '3 Nefi 18:22' },
  baptism_doctrine_lessons:  { slug: 'BAPDOCTRINE',   chapter: 'Capítulo 12', pmgDesc: 'Enseñar la doctrina del bautismo',                     scripture: '3 Nefi 11:33' },
  baptismal_invitations:     { slug: 'BAPINVITE',     chapter: 'Capítulo 11', pmgDesc: 'Extender la invitación bautismal',                     scripture: '3 Nefi 27:20' },
  baptismal_calendars:       { slug: 'BAPCALENDAR',   chapter: 'Capítulo 12', pmgDesc: 'Preparar para el bautismo y la confirmación',          scripture: '2 Nefi 31:17' }
};

// =============================================================================
// PER-ROW OVERRIDES — the two rows the task brief supplied verbatim as
// illustrative examples. Their page-number PMG style and Scripture_Text were
// never verified against the Spanish LDS edition, so both are normalized here
// to the same chapter-level PMG / blank-Scripture_Text convention as the
// other 191 rows (content rule 1). Scripture references are kept — only the
// quoted verse wording and the page numbers were uncertain.
// =============================================================================
var CSC_ROW_OVERRIDES = {
  'MSG-CS-ROLEPLAYS-01': {
    pmgChapter:     'Capítulo 10',
    pmgDescription: 'La práctica mejora la enseñanza',
    scripture:      'D. y C. 84:85',
    scriptureText:  ''
  },
  'MSG-CG-CONTACTS-01': {
    pmgChapter:     'Capítulo 9',
    pmgDescription: 'Hablar con todos',
    scripture:      'D. y C. 33:8-10',
    scriptureText:  ''
  }
};

// =============================================================================
// SUNDAY_COACHING_STRENGTH — sent when an area did WELL on the metric.
// Three variants per metric so pickMessage()'s no-repeat filter always has
// somewhere to go (CCSM_Helpers.gs pickMessage()).
// =============================================================================
var CSC_STRENGTH = {
  contact_rate: [
    ['La gente se detiene a escucharles',
     'Esta semana una buena parte de sus intentos se convirtió en un contacto real. Eso dice mucho de la manera amable y sincera con que ustedes se acercan a las personas. Sigan acercándose con esa misma calidez.'],
    ['Constancia que se nota',
     'Su tasa de contacto se mantuvo firme durante toda la semana. La obra del Señor se edifica más con la constancia diaria que con un solo día extraordinario. Gracias por su esfuerzo fiel.'],
    ['Un acercamiento que abre puertas',
     'Muchas de las personas con quienes ustedes intentaron hablar respondieron. Cuando el amor por los demás se nota antes que las palabras, el corazón se abre. Sigan orando por cada persona antes de saludarla.']
  ],
  mc_rate: [
    ['Conversaciones que llegan al corazón',
     'Buena parte de sus contactos se transformó en una conversación significativa. Eso ocurre cuando ustedes escuchan de verdad y preguntan con interés sincero. El Espíritu enseña mejor donde hay confianza.'],
    ['Saben escuchar',
     'Su área se destacó esta semana en conversaciones significativas. Escuchar es una forma de amar, y las personas lo sienten de inmediato. Sigan dando tiempo a cada persona para contar su historia.'],
    ['Del saludo a la conversación',
     'Muchos de sus contactos pasaron del saludo a una conversación de verdad. Ese paso es justamente donde comienza la enseñanza. Gracias por no conformarse con un simple saludo.']
  ],
  lesson_rate: [
    ['De la calle a la lección',
     'Esta semana un buen número de sus contactos terminó en una lección. Eso significa que ustedes están invitando a aprender en el momento oportuno. Sigan ofreciendo la primera lección desde el primer encuentro.'],
    ['Invitaciones oportunas',
     'Su tasa de lecciones estuvo entre las más altas de la misión. Cuando se invita con fe, muchas más personas dicen que sí de lo que uno imagina. Gracias por atreverse a preguntar.'],
    ['Enseñar desde el primer momento',
     'Muchos de sus contactos recibieron algo de enseñanza el mismo día. No hay mejor manera de comenzar una amistad en el evangelio. Sigan compartiendo un mensaje breve siempre que puedan.']
  ],
  close_rate: [
    ['Invitan con fe',
     'Su área extendió la invitación al bautismo en una buena parte de sus lecciones. Invitar es un acto de fe y de amor por la persona. Sigan confiando en que el Señor prepara a sus hijos.'],
    ['No temen invitar',
     'Esta semana muchas de sus lecciones incluyeron una invitación bautismal. Las personas necesitan escuchar la invitación para poder aceptarla. Gracias por su valentía.'],
    ['Enseñan con un propósito claro',
     'Sus lecciones llevaron a las personas hacia el convenio del bautismo. Enseñar con ese propósito bendice a quienes escuchan. Sigan enseñando con esa claridad.']
  ],
  effort_score: [
    ['Lo dieron todo en el altar',
     'Su área informó un nivel de esfuerzo muy alto esta semana. Ofrecer el día entero al Señor es la ofrenda más sincera que un misionero puede dar. Él conoce y honra ese esfuerzo.'],
    ['Días bien entregados',
     'Semana tras semana ustedes están entregando lo mejor de sus fuerzas. Ese esfuerzo constante los está transformando, aunque no siempre se vea en los números. Descansen bien y sigan adelante.'],
    ['Un esfuerzo que se nota',
     'El nivel de esfuerzo de su área fue de los más altos de la semana. Trabajar con todo el corazón, alma, mente y fuerza es lo que el Señor pide. Gracias por darlo todo.']
  ],
  roleplays: [
    ['¡Su preparación se nota!',
     'Esta semana su área se destacó en las prácticas de enseñanza. El Señor honra la preparación diligente: cada práctica les acerca más a enseñar con el Espíritu. ¡Sigan así!'],
    ['Practicar juntos da fruto',
     'Su compañerismo dedicó buen tiempo a las prácticas de enseñanza esta semana. Practicar hace que las palabras salgan con naturalidad cuando llega el momento real. Sigan reservando ese tiempo cada día.'],
    ['Preparados para enseñar',
     'Las prácticas de esta semana muestran un compañerismo que se prepara en serio. Enseñar bien no es un don repentino, sino el fruto de la preparación. Gracias por su diligencia.']
  ],
  contacts_attempted: [
    ['Hablaron con muchos',
     'Su área hizo un gran número de intentos de contacto esta semana. Cada intento es una manera de decirle al Señor que están dispuestos. Sigan abriendo la boca cada día.'],
    ['No se guardaron el mensaje',
     'Esta semana su compañerismo buscó a la gente sin descanso. Nunca sabemos cuál conversación cambiará una vida, y por eso siempre vale la pena intentarlo. Gracias por su valentía.'],
    ['Valentía diaria',
     'Los intentos de contacto de su área estuvieron entre los más altos de la semana. Hablar con desconocidos requiere fe, y ustedes la demostraron día tras día. Sigan adelante con ese ánimo.']
  ],
  contacts_made: [
    ['Conversaciones logradas',
     'Su área logró muchos contactos reales esta semana. Detrás de cada número hay una persona que se sintió tratada con respeto. Gracias por ese trato.'],
    ['Saben acercarse',
     'Los contactos de su área fueron de los más altos de la semana. Acercarse con naturalidad es una habilidad que se aprende, y ustedes la están desarrollando. Sigan practicando.'],
    ['Un rostro para cada número',
     'Esta semana muchas personas se detuvieron a conversar con ustedes. Recuerden orar por ellas por su nombre, porque el Señor conoce a cada una. Sigan cuidando esas primeras impresiones.']
  ],
  meaningful_conversations: [
    ['Conversaciones con profundidad',
     'Su área tuvo muchas conversaciones significativas esta semana. Hablar de lo que de verdad importa es donde comienza la conversión. Sigan llevando las conversaciones a ese terreno.'],
    ['Escuchan con el corazón',
     'Las conversaciones significativas de su compañerismo fueron muchas esta semana. Eso solo ocurre cuando la persona siente que le importa a alguien. Gracias por su cariño hacia la gente.'],
    ['Preguntas que abren el corazón',
     'Esta semana lograron que muchas personas les contaran algo importante de su vida. Una buena pregunta hace más que un buen discurso. Sigan preguntando con interés sincero.']
  ],
  new_people_found: [
    ['Nuevos amigos del evangelio',
     'Su área encontró varias personas nuevas a quienes enseñar esta semana. Cada una de ellas llegó porque ustedes salieron a buscarla. Sigan orando por ellas por su nombre.'],
    ['Una obra que crece',
     'Las nuevas personas encontradas por su compañerismo fueron muchas esta semana. Hallar es un trabajo de fe, y ustedes lo hicieron con constancia. Gracias por su diligencia.'],
    ['El Señor prepara a sus hijos',
     'Esta semana varias personas nuevas aceptaron ser enseñadas en su área. El Señor va delante preparando corazones, y ustedes llegaron a tiempo. Sigan buscando con esa misma fe.']
  ],
  friend_lessons: [
    ['Muchas lecciones enseñadas',
     'Su área enseñó un buen número de lecciones esta semana. Enseñar es el corazón de la obra misional, y ustedes le dedicaron su tiempo. Sigan preparando cada lección con oración.'],
    ['Enseñanza constante',
     'Las lecciones con amigos de su compañerismo fueron muchas esta semana. La enseñanza frecuente ayuda a que la fe crezca sin interrupciones. Gracias por cuidar ese ritmo.'],
    ['Tiempo bien invertido',
     'Esta semana su área dedicó gran parte del tiempo a enseñar. Nada de lo que hace un misionero bendice tanto como una lección enseñada con el Espíritu. Sigan así.']
  ],
  pmf_lessons: [
    ['Bendicen a familias',
     'Esta semana su área enseñó a varias familias en las que no todos son miembros. Ayudar a una familia a unirse en el evangelio es una obra eterna. Sigan visitándolas con cariño.'],
    ['Un hogar a la vez',
     'Las lecciones con familias parciales de su área fueron muchas. Cuando un integrante de la familia siente el Espíritu, todo el hogar cambia. Gracias por su paciencia con ellas.'],
    ['Trabajo que une hogares',
     'Su compañerismo dedicó tiempo a las familias en las que no todos son miembros. Esas visitas fortalecen tanto al miembro como a quien todavía no lo es. Sigan orando por cada hogar.']
  ],
  rc_lessons: [
    ['Cuidan a los nuevos miembros',
     'Su área enseñó a varios conversos recientes esta semana. Un nuevo miembro necesita ser nutrido por la buena palabra de Dios. Gracias por acompañarlos.'],
    ['El bautismo no es el final',
     'Las lecciones con conversos recientes de su área fueron muchas. Seguir enseñando después del bautismo es lo que sostiene la conversión. Sigan visitándolos con constancia.'],
    ['Amistad que sostiene',
     'Esta semana dedicaron tiempo a los conversos recientes de su área. Ese acompañamiento hace la diferencia entre permanecer y alejarse. Sigan siendo sus amigos.']
  ],
  rc_lessons_mcp: [
    ['Mi Senda de los Convenios en uso',
     'Su área usó Mi Senda de los Convenios con varios conversos recientes esta semana. Ese recurso ayuda a que el nuevo miembro vea con claridad el camino del convenio. Sigan usándolo en cada visita.'],
    ['Enseñar el camino del convenio',
     'Esta semana enseñaron con Mi Senda de los Convenios en varias visitas. Cuando el nuevo miembro entiende sus convenios, los guarda con más gozo. Gracias por enseñar con ese enfoque.'],
    ['Un camino claro',
     'Las lecciones con Mi Senda de los Convenios de su área fueron muchas. Ese material ordena la enseñanza y le da al converso reciente algo concreto que seguir. Sigan aprovechándolo.']
  ],
  friend_texts: [
    ['Seguimiento constante',
     'Su área envió muchos mensajes a sus amigos esta semana. Un mensaje corto entre visitas le hace saber a la persona que se acuerdan de ella. Sigan cuidando ese contacto.'],
    ['Un mensaje que anima',
     'Esta semana escribieron a sus amigos con constancia. Compartir un versículo o una palabra de ánimo mantiene viva la fe entre una lección y la siguiente. Gracias por ese detalle.'],
    ['Presentes durante la semana',
     'Los mensajes enviados por su compañerismo fueron muchos. Estar presentes durante la semana ayuda a que la cita del fin de semana no se olvide. Sigan escribiendo con cariño.']
  ],
  friend_calls: [
    ['Una voz amiga',
     'Su área hizo muchas llamadas a sus amigos esta semana. Escuchar una voz conocida da un ánimo que un mensaje escrito no alcanza a dar. Sigan llamando.'],
    ['Seguimiento con cariño',
     'Las llamadas de su compañerismo fueron muchas esta semana. Llamar antes de una cita muestra respeto por el tiempo de la persona. Gracias por ese cuidado.'],
    ['Cerca aunque no estén',
     'Esta semana llamaron a sus amigos con constancia. Una llamada breve mantiene viva la relación cuando no se puede visitar. Sigan usando ese recurso.']
  ],
  member_contacts: [
    ['Unidos con el barrio',
     'Su área tuvo muchos contactos con miembros esta semana. La obra avanza cuando misioneros y miembros trabajan con un solo corazón. Sigan cultivando esa amistad.'],
    ['Los miembros como aliados',
     'Esta semana conversaron con muchos miembros del barrio. Cada miembro conoce personas que ustedes nunca alcanzarían solos. Gracias por acercarse a ellos.'],
    ['Confianza que se construye',
     'Los contactos con miembros de su compañerismo fueron muchos. La confianza del barrio se gana visitando y escuchando, y ustedes lo están haciendo. Sigan así.']
  ],
  lessons_member_present: [
    ['Enseñaron acompañados',
     'Varias de sus lecciones de esta semana contaron con un miembro presente. Cuando un miembro acompaña, el amigo gana una amistad que permanece. Sigan invitándolos.'],
    ['Un amigo en el barrio',
     'Esta semana muchos miembros les acompañaron a enseñar. El testimonio de un miembro del lugar toca de una manera distinta. Gracias por incluirlos.'],
    ['Enseñanza compartida',
     'Su área enseñó con un miembro presente en buena parte de sus lecciones. Así el amigo ya conoce a alguien antes de entrar por la puerta de la capilla. Sigan trabajando de esa manera.']
  ],
  references_asked: [
    ['Se atrevieron a pedir',
     'Su área pidió muchas referencias esta semana. Preguntar a quién más podrían visitar es una de las maneras más eficaces de hallar. Sigan preguntando siempre.'],
    ['Preguntar abre puertas',
     'Esta semana pidieron referencias con constancia. Casi todos conocen a alguien que necesita el evangelio, pero hay que preguntar. Gracias por hacerlo.'],
    ['Un hábito que rinde',
     'Las referencias solicitadas por su compañerismo fueron muchas. Convertir esa pregunta en un hábito al final de cada visita cambia por completo la obra de hallar. Sigan con ese hábito.']
  ],
  member_referrals_received: [
    ['El barrio confía en ustedes',
     'Su área recibió varias referencias de miembros esta semana. Los miembros comparten nombres cuando ven que los misioneros cuidan bien a las personas. Sigan contándoles cómo le va a cada una.'],
    ['Referencias que llegan',
     'Esta semana los miembros del barrio les entregaron varias referencias. Esa confianza se gana con trabajo constante y con buenas noticias de vuelta. Gracias por cultivarla.'],
    ['Trabajo con el barrio',
     'Las referencias recibidas de miembros fueron muchas esta semana. Las personas que llegan por medio de un amigo suelen progresar más rápido. Sigan trabajando de la mano con el barrio.']
  ],
  bom_shared: [
    ['Entregaron el libro',
     'Su área entregó varios ejemplares del Libro de Mormón esta semana. Ese libro sigue enseñando cuando ustedes ya no están presentes. Sigan poniéndolo en manos de la gente.'],
    ['Otro testamento de Jesucristo',
     'Esta semana muchas personas recibieron el Libro de Mormón de sus manos. Es otro testamento de Jesucristo y tiene poder para convertir. Gracias por compartirlo con fe.'],
    ['El libro abre el camino',
     'Los ejemplares entregados por su compañerismo fueron muchos. Cuando alguien lee y ora, el Espíritu Santo confirma la verdad. Sigan invitando a leer y a orar.']
  ],
  church_invites: [
    ['Invitan a venir',
     'Su área extendió muchas invitaciones a la Iglesia esta semana. Sentir el Espíritu en la reunión sacramental fortalece la fe como pocas cosas. Sigan invitando a todos.'],
    ['Las puertas abiertas',
     'Esta semana invitaron a muchas personas a asistir a la Iglesia. Nadie debe quedar fuera cuando desea venir a adorar. Gracias por invitar con tanto ánimo.'],
    ['Una invitación sencilla',
     'Las invitaciones a la Iglesia de su compañerismo fueron muchas. Invitar es sencillo, pero le cambia la vida a quien acepta. Sigan haciéndolo cada día.']
  ],
  baptism_doctrine_lessons: [
    ['Enseñan la doctrina',
     'Su área enseñó la doctrina del bautismo en varias lecciones esta semana. Cuando la doctrina se entiende, el convenio se hace con gozo. Sigan enseñando con claridad.'],
    ['Claridad que bendice',
     'Esta semana muchas de sus lecciones incluyeron la doctrina del bautismo. Enseñar el porqué del convenio prepara mucho mejor que solo fijar una fecha. Gracias por enseñarlo bien.'],
    ['El camino del convenio',
     'Su compañerismo enseñó el bautismo como parte del camino del convenio. Así la persona ve el bautismo como un comienzo y no como una meta final. Sigan con ese enfoque.']
  ],
  baptismal_invitations: [
    ['Invitaron con fe',
     'Su área extendió varias invitaciones al bautismo esta semana. Invitar es un acto de amor, porque nadie puede aceptar lo que no se le ofrece. Sigan invitando con confianza.'],
    ['Valentía para invitar',
     'Esta semana muchas personas recibieron de ustedes una invitación al bautismo. Se necesita fe para preguntar, y ustedes la tuvieron. Gracias por su valor.'],
    ['Invitaciones sinceras',
     'Las invitaciones al bautismo de su compañerismo fueron muchas. Cuando la invitación nace del cariño, la persona lo siente aunque responda que todavía no. Sigan invitando así.']
  ],
  baptismal_calendars: [
    ['Un camino con fechas',
     'Su área entregó varios calendarios bautismales esta semana. Ver el camino escrito le ayuda al amigo a saber qué viene después. Sigan usándolos en sus lecciones.'],
    ['Preparación ordenada',
     'Esta semana entregaron calendarios bautismales a varias personas. Un plan claro convierte un buen deseo en una preparación real. Gracias por enseñar con orden.'],
    ['Del deseo al plan',
     'Los calendarios entregados por su compañerismo fueron muchos. Cuando la persona ve las fechas, se compromete con más facilidad. Sigan haciéndolo así.']
  ]
};

// =============================================================================
// SUNDAY_COACHING_GROWTH — sent when an area NEEDS IMPROVEMENT on the metric.
// Every row names one concrete, doable next step. Never guilt, never a promise
// of a specific outcome.
// =============================================================================
var CSC_GROWTH = {
  contact_rate: [
    ['Un poco más de calidez al acercarse',
     'Esta semana varios intentos no llegaron a ser una conversación. Prueben comenzar con una pregunta sencilla sobre la persona antes de hablar del mensaje. Elijan juntos una frase inicial y practíquenla mañana.'],
    ['Menos prisa, más conexión',
     'Su tasa de contacto bajó un poco respecto de lo acostumbrado. A veces ayuda bajar el ritmo: mirar a los ojos, saludar sin apuro y escuchar la respuesta completa. Una conversación tranquila vale más que diez saludos apurados.'],
    ['Prueben otro lugar y otra hora',
     'Cuando pocos intentos se convierten en contactos, muchas veces el asunto no es el mensaje sino el momento. Conversen en su planificación sobre dónde y cuándo la gente de su área está más dispuesta a hablar. Prueben un lugar nuevo esta semana.']
  ],
  mc_rate: [
    ['Una pregunta más antes de despedirse',
     'Esta semana pocos contactos llegaron a ser conversaciones significativas. Antes de despedirse, hagan una pregunta más sobre lo que hoy le preocupa a esa persona. Escuchen la respuesta sin apuro.'],
    ['Escuchar antes de enseñar',
     'Sus conversaciones se quedaron cortas esta semana. Cuando se habla mucho y se escucha poco, la persona no alcanza a abrir su corazón. Propónganse escuchar el doble de lo que hablan.'],
    ['Hablen de lo que a ella le importa',
     'Varias conversaciones terminaron antes de volverse significativas. Traten de conectar el mensaje con lo que la persona ya les contó de su vida y de su familia. El evangelio responde a necesidades reales.']
  ],
  lesson_rate: [
    ['Ofrezcan la lección en el momento',
     'Esta semana pocos contactos se convirtieron en lecciones. Prueben compartir un mensaje corto allí mismo, en lugar de dejarlo para una cita futura. Muchas personas aceptan cuando la invitación llega de inmediato.'],
    ['Una invitación clara',
     'Varias conversaciones terminaron sin una invitación concreta a aprender más. Practiquen juntos una forma sencilla y directa de ofrecer la primera lección. La claridad ayuda a que la persona sepa qué se le está ofreciendo.'],
    ['Del interés al compromiso',
     'Hubo interés esta semana, pero pocas lecciones. Cuando alguien muestre interés, propongan un día y una hora antes de despedirse. Un plan concreto convierte el interés en enseñanza.']
  ],
  close_rate: [
    ['Inviten temprano',
     'Esta semana pocas lecciones terminaron con una invitación bautismal. Prueben extender la invitación en la primera lección, mientras el Espíritu esté presente. Invitar temprano le da tiempo a la persona para prepararse.'],
    ['Preparen la invitación',
     'Varias lecciones terminaron sin invitación. Antes de cada cita, decidan juntos quién invitará y con qué palabras. Prepararlo de antemano le quita el nerviosismo al momento.'],
    ['Confíen en la preparación del Señor',
     'A veces esperamos a que la persona esté lista y dejamos pasar la invitación. Recuerden que la invitación misma ayuda a preparar el corazón. Escojan a una persona e invítenla esta semana.']
  ],
  effort_score: [
    ['Comiencen el día con una meta',
     'Esta semana el nivel de esfuerzo bajó un poco. Al comenzar cada día, escojan juntos una sola cosa que quieran lograr y protéjanla. Una meta clara ayuda a mantener el ánimo.'],
    ['Cuiden el descanso y la salud',
     'Un esfuerzo bajo muchas veces es señal de cansancio y no de falta de deseo. Cuiden el horario de dormir, la comida y el ejercicio, porque el cuerpo sostiene al espíritu. Hablen con sus líderes si algo les está pesando.'],
    ['Vuelvan a su propósito',
     'Cuando el esfuerzo cuesta, ayuda recordar por qué están en la misión. Lean juntos su llamamiento y oren por las personas de su área por su nombre. El propósito renueva las fuerzas.']
  ],
  roleplays: [
    ['Diez minutos cada mañana',
     'Esta semana hubo pocas prácticas de enseñanza. Prueben apartar diez minutos al final del estudio de compañerismo para practicar una sola parte de la lección. Poco tiempo, todos los días, hace una gran diferencia.'],
    ['Practiquen lo que viene',
     'Las prácticas bajaron esta semana. Escojan la cita más importante de mañana y ensayen juntos cómo comenzarán y qué invitación harán. Llegarán con mucha más confianza.'],
    ['Túrnense para enseñar',
     'Cuando faltan las prácticas, la enseñanza se vuelve improvisada. Túrnense: uno hace de amigo y el otro enseña, y luego cambien. Es la manera más rápida de mejorar juntos.']
  ],
  contacts_attempted: [
    ['Una invitación: abran la boca',
     'Esta semana hubo menos intentos de contacto que de costumbre. Recuerden que cada persona es un hijo de Dios que espera escuchar el evangelio. Fijen una meta pequeña para mañana: cinco intentos más que hoy.'],
    ['Un plan para los tiempos libres',
     'Esta semana hubo pocos intentos de contacto. Revisen su horario y decidan qué harán cuando una cita se cancele o quede un espacio libre. Un plan sencillo evita perder esos minutos.'],
    ['Hablen mientras caminan',
     'Los intentos de contacto bajaron respecto de lo acostumbrado. Propónganse saludar a cada persona que pase junto a ustedes mientras van de una cita a otra. Muchas conversaciones comienzan justo allí.']
  ],
  contacts_made: [
    ['Del intento al contacto',
     'Esta semana hubo bastantes intentos, pero pocos contactos completos. Prueben cambiar la primera frase: en vez de presentar el mensaje, pregunten algo sobre la persona. Escuchar primero abre la conversación.'],
    ['Sonrían y pregunten el nombre',
     'Los contactos de su área bajaron un poco. Un saludo con el nombre de la persona y una sonrisa sincera cambian por completo la respuesta de la gente. Prueben pedir el nombre al comenzar.'],
    ['Busquen donde la gente se detiene',
     'Cuando cuesta lograr contactos, ayuda cambiar de lugar. Busquen plazas, ferias o paraderos donde la gente ya está esperando y dispuesta a conversar. Prueben uno de esos lugares esta semana.']
  ],
  meaningful_conversations: [
    ['Una pregunta sobre la familia',
     'Esta semana hubo pocas conversaciones significativas. Prueben preguntar por la familia o por lo que la persona espera para los suyos. Casi siempre esa puerta se abre.'],
    ['Dejen espacio al silencio',
     'Sus conversaciones se quedaron en lo superficial esta semana. Después de preguntar, esperen unos segundos en silencio, porque muchas veces allí llega la respuesta verdadera. Practíquenlo mañana.'],
    ['Conecten el evangelio con su vida',
     'Pocas conversaciones llegaron a ser significativas. Escuchen primero la necesidad y luego muestren cómo el evangelio de Jesucristo responde a ella. Así la conversación deja de ser una charla más.']
  ],
  new_people_found: [
    ['Prueben una fuente nueva',
     'Esta semana se encontraron pocas personas nuevas. Además de contactar en la calle, pidan referencias a los miembros y a las personas que ya están aprendiendo. Los mejores encuentros suelen llegar por medio de un conocido.'],
    ['Planifiquen dónde buscar',
     'El número de personas nuevas bajó esta semana. En la planificación semanal, escojan dos sectores concretos y sus horarios para buscar. Un plan claro rinde más que salir a ver qué pasa.'],
    ['Vuelvan a los antiguos amigos',
     'A veces las personas nuevas están más cerca de lo que parece. Revisen su registro de personas con quienes hablaron hace meses y visítenlas otra vez. Las circunstancias cambian, y el corazón también.']
  ],
  friend_lessons: [
    ['Aseguren la próxima cita',
     'Esta semana hubo pocas lecciones. Antes de terminar cada visita, fijen el día y la hora de la siguiente. Una cita acordada rinde mucho más que una promesa de pasar.'],
    ['Enseñen aunque sea breve',
     'Las lecciones bajaron esta semana. Una lección corta en la puerta, con una escritura y una invitación, también cuenta y también bendice. No esperen siempre la visita perfecta.'],
    ['Revisen la lista de amigos',
     'Pocas lecciones esta semana pueden significar que hay amigos sin visitar. Revisen juntos su lista y escojan a tres personas para visitar mañana. Muchas veces solo falta volver a tocar la puerta.']
  ],
  pmf_lessons: [
    ['Pregunten al obispo',
     'Esta semana hubo pocas lecciones con familias en las que no todos son miembros. Pidan al obispo o a los líderes del barrio los nombres de esos hogares. Ellos conocen a las familias que más necesitan una visita.'],
    ['Visiten sin presionar',
     'Estas lecciones bajaron esta semana. Ofrezcan una visita breve para compartir un mensaje con toda la familia, sin condiciones ni presiones. La confianza se construye de a poco.'],
    ['Inviten a la familia completa',
     'Cuando enseñen a un integrante de la familia, inviten a los demás a acompañarlos. Muchas veces alguien escucha desde otra habitación y termina participando. Prueben incluirlos esta semana.']
  ],
  rc_lessons: [
    ['Aparten un día para ellos',
     'Esta semana hubo pocas lecciones con conversos recientes. Escojan un día fijo de la semana para visitarlos y protéjanlo en su horario. La constancia es lo que más los fortalece.'],
    ['Enseñen con un miembro',
     'Estas lecciones bajaron esta semana. Inviten a un miembro del barrio a acompañarles, para que el converso reciente gane un amigo además de una lección. La amistad local es lo que permanece.'],
    ['Pregunten cómo van',
     'Cuando faltan visitas, los conversos recientes pueden sentirse solos. Llamen a cada uno esta semana y pregunten cómo van sus oraciones y su lectura. Una llamada breve abre la puerta a una visita.']
  ],
  rc_lessons_mcp: [
    ['Lleven el material consigo',
     'Esta semana se usó poco Mi Senda de los Convenios. Llévenlo siempre con ustedes para poder abrirlo en cualquier visita. Tenerlo a mano es la mitad del trabajo.'],
    ['Una sección por visita',
     'El uso de Mi Senda de los Convenios bajó esta semana. Escojan una sola sección para cada visita y dejen una tarea sencilla al converso reciente. Avanzar de a poco enseña mejor que apurar.'],
    ['Planifiquen su uso',
     'Cuando no se planifica, este recurso queda sin usar. En su planificación semanal, anoten qué sección enseñarán a cada converso reciente. Así la visita ya llega preparada.']
  ],
  friend_texts: [
    ['Escriban después de cada visita',
     'Esta semana se enviaron pocos mensajes a los amigos. Tomen el hábito de escribir un agradecimiento breve al salir de cada lección. Es rápido y deja una huella cálida.'],
    ['Un versículo cada mañana',
     'Los mensajes a los amigos bajaron esta semana. Prueben enviar cada mañana un versículo corto a dos personas distintas. La constancia importa más que la extensión.'],
    ['Recuerden la cita',
     'Cuando no se escribe, muchas citas se olvidan. Envíen un recordatorio amable el día anterior a cada visita. Verán menos citas perdidas.']
  ],
  friend_calls: [
    ['Aparten quince minutos',
     'Esta semana hubo pocas llamadas a los amigos. Aparten quince minutos fijos cada día para llamar a quienes no alcanzaron a visitar. Un horario fijo lo hace posible.'],
    ['Llamen para confirmar',
     'Las llamadas bajaron esta semana. Confirmen por teléfono cada cita el mismo día, porque eso evita viajes perdidos y muestra respeto. Es un hábito que ahorra mucho tiempo.'],
    ['Llamen a quienes no ven hace tiempo',
     'Cuando hay pocas llamadas, algunos amigos quedan sin noticias. Hagan una lista de quienes no ven hace dos semanas y llámenlos. Una llamada puede reabrir una puerta.']
  ],
  member_contacts: [
    ['Visiten a una familia por día',
     'Esta semana hubo pocos contactos con miembros. Propónganse visitar a una familia del barrio cada día, aunque sea por diez minutos. La relación con el barrio se construye visita a visita.'],
    ['Compartan sus planes',
     'Los contactos con miembros bajaron esta semana. Cuéntenles a los miembros a quiénes están enseñando y qué necesitan, porque muchos querrán ayudar. La ayuda llega cuando se sabe qué hace falta.'],
    ['Aprovechen el domingo',
     'Cuando hay pocos contactos con miembros, el domingo es la mejor oportunidad. Lleguen temprano a la reunión y conversen con varias familias antes de irse. Es tiempo muy bien aprovechado.']
  ],
  lessons_member_present: [
    ['Inviten con anticipación',
     'Esta semana hubo pocas lecciones con un miembro presente. Inviten a los miembros con dos o tres días de anticipación y díganles qué se espera de ellos. Con tiempo, muchos más aceptan.'],
    ['Pidan un testimonio breve',
     'Cuando el miembro sabe que solo compartirá un testimonio breve, acepta con mucha más facilidad. Prueben invitarlo de esa manera esta semana. Su presencia vale más que muchas palabras.'],
    ['Hagan una lista de acompañantes',
     'Pocas lecciones tuvieron un miembro presente. Preparen con el obispo o con el líder misional una lista de miembros dispuestos a acompañarles. Tener a quién llamar lo hace mucho más fácil.']
  ],
  references_asked: [
    ['Pregunten al final de cada visita',
     'Esta semana se pidieron pocas referencias. Antes de despedirse de cualquier persona, pregunten a quién más podrían visitar. Es una sola frase y cuesta muy poco.'],
    ['Pregunten por alguien concreto',
     'Cuando la pregunta es general, la respuesta suele ser ninguna. Prueben preguntar por un vecino, un familiar o un compañero de trabajo. Las preguntas concretas reciben respuestas concretas.'],
    ['Pidan también a los amigos',
     'Las referencias bajaron esta semana. No pidan solo a los miembros, porque los amigos que están aprendiendo también conocen personas interesadas. Inclúyanlos en la pregunta.']
  ],
  member_referrals_received: [
    ['Cuenten los resultados',
     'Esta semana llegaron pocas referencias de miembros. Cuando visiten a una persona referida, avisen al miembro cómo resultó la visita. Al ver los frutos, los miembros vuelven a referir.'],
    ['Expliquen a quién buscan',
     'Las referencias de miembros bajaron esta semana. En la reunión de coordinación, describan qué tipo de persona están buscando y por qué. Cuando se sabe a quién buscar, es más fácil pensar en alguien.'],
    ['Visiten pronto a los referidos',
     'Cuando una referencia demora en ser visitada, el miembro deja de referir. Propónganse contactar a cada persona referida dentro del primer día. La rapidez construye confianza.']
  ],
  bom_shared: [
    ['Lleven ejemplares consigo',
     'Esta semana se entregaron pocos ejemplares del Libro de Mormón. Lleven siempre dos o tres consigo para poder entregarlos en el momento oportuno. No se puede compartir lo que no se lleva.'],
    ['Marquen un pasaje',
     'La entrega de libros bajó esta semana. Antes de entregar un ejemplar, marquen un pasaje y pidan a la persona que lo lea antes de la próxima visita. Así el libro se abre de verdad.'],
    ['Compartan su testimonio del libro',
     'Cuando entregamos el libro sin testificar, muchas veces queda en un estante. Cuéntenle a la persona qué ha significado ese libro para cada uno de ustedes. Un testimonio sincero invita a leer.']
  ],
  church_invites: [
    ['Inviten con detalles',
     'Esta semana hubo pocas invitaciones a la Iglesia. Cuando inviten, digan la hora y la dirección, y ofrézcanse a acompañar a la persona. Los detalles le quitan el temor de llegar sola.'],
    ['Inviten a todos',
     'Las invitaciones bajaron esta semana. Inviten a cada persona con quien conversen, aunque parezca poco interesada. Muchos aceptan cuando alguien por fin se lo pide.'],
    ['Pidan a un miembro que la reciba',
     'Cuando el amigo no conoce a nadie, cuesta mucho que llegue. Pidan a una familia del barrio que lo reciba en la puerta y se siente con él. Sentirse esperado hace toda la diferencia.']
  ],
  baptism_doctrine_lessons: [
    ['Enséñenla desde la primera lección',
     'Esta semana se enseñó poco la doctrina del bautismo. Inclúyanla desde la primera visita, aunque sea brevemente. Cuanto antes se entiende, antes se desea.'],
    ['Usen las Escrituras',
     'Estas lecciones bajaron esta semana. Enseñen el bautismo con las palabras del Salvador en las Escrituras y no solo con las propias. La palabra de Dios convence de una manera distinta.'],
    ['Pregunten qué entendieron',
     'Después de enseñar la doctrina, pidan a la persona que explique con sus palabras lo que comprendió. Allí verán con claridad qué falta aclarar. Enseñar es asegurarse de que se entendió.']
  ],
  baptismal_invitations: [
    ['Inviten en la primera lección',
     'Esta semana hubo pocas invitaciones al bautismo. Prueben extender la invitación en la primera lección, mientras el Espíritu esté presente. Invitar temprano da tiempo para prepararse.'],
    ['Decidan quién invitará',
     'Las invitaciones bajaron esta semana. Antes de cada cita, acuerden quién hará la invitación y con qué palabras. Prepararlo evita que el momento pase de largo.'],
    ['Un no de hoy no cierra la puerta',
     'A veces dejamos de invitar por temor a una respuesta negativa. Un no de hoy suele ser un todavía no, y la invitación siembra de igual manera. Vuelvan a invitar con paciencia y cariño.']
  ],
  baptismal_calendars: [
    ['Entréguenlo al invitar',
     'Esta semana se entregaron pocos calendarios bautismales. Al extender la invitación, muestren el calendario y planifiquen juntos las fechas. El plan hace concreta la invitación.'],
    ['Complétenlo con la persona',
     'La entrega de calendarios bajó esta semana. En vez de entregarlo ya escrito, complétenlo junto con el amigo durante la lección. Participar en el plan lo hace suyo.'],
    ['Revísenlo en cada visita',
     'Un calendario que no se revisa se olvida. Ábranlo en cada visita y celebren juntos lo que ya se cumplió. El progreso visible anima a seguir.']
  ]
};

// =============================================================================
// FRIDAY_ENCOURAGEMENT — a mid-week nudge toward a weekly COUNT goal
// (CCSM_Agent5B.gs). Count metrics only: rate metrics have no weekly count
// goal to close in on.
// =============================================================================
var CSC_FRIDAY = {
  roleplays: [
    ['Una práctica antes de salir',
     'Es viernes y todavía hay tiempo para acercarse a su meta de prácticas de enseñanza. Antes de salir hoy, ensayen juntos la primera lección durante unos minutos. Verán la diferencia en su próxima cita.'],
    ['Terminen la semana preparados',
     'Quedan pocos días de la semana y su meta de prácticas está a su alcance. Elijan una parte de la lección que les cueste y practíquenla dos veces hoy. La preparación de hoy bendice a alguien mañana.']
  ],
  contacts_attempted: [
    ['Aún hay tiempo esta semana',
     'Es viernes y su meta de intentos de contacto todavía está al alcance. Fijen un número para hoy y cúmplanlo antes de volver a casa. El Señor bendice cada intento sincero.'],
    ['Una meta para hoy',
     'Quedan días para llegar a su meta de intentos de contacto. Escojan una calle o un sector nuevo y saluden a todas las personas que puedan. Cada una de ellas es un hijo de Dios.']
  ],
  contacts_made: [
    ['Terminen la semana conversando',
     'Es viernes y su meta de contactos todavía se puede alcanzar. Propónganse conocer hoy el nombre de cinco personas nuevas. Un nombre es el comienzo de una amistad.'],
    ['Un empujón para la meta',
     'Su área está cerca de su meta de contactos de esta semana. Aprovechen las horas de mayor movimiento en su sector para conversar sin apuro. Ustedes pueden lograrlo.']
  ],
  meaningful_conversations: [
    ['Una conversación de verdad hoy',
     'Es viernes y su meta de conversaciones significativas está cerca. Escojan hoy a tres personas y dedíquenles tiempo sin apuro. Una conversación sincera vale por muchas.'],
    ['Vayan más allá del saludo',
     'Todavía pueden alcanzar su meta de conversaciones significativas. Con cada persona que saluden hoy, hagan una segunda pregunta antes de despedirse. Allí suele comenzar lo importante.']
  ],
  new_people_found: [
    ['Alguien les está esperando',
     'Es viernes y su meta de personas nuevas todavía se puede alcanzar. Salgan hoy con la oración de encontrar a una persona preparada. El Señor sabe dónde está.'],
    ['Una persona más esta semana',
     'Su área está cerca de su meta de nuevas personas encontradas. Pidan una referencia en cada visita de hoy. Una sola referencia puede completar la semana.']
  ],
  friend_lessons: [
    ['Una lección más hoy',
     'Es viernes y su meta de lecciones está al alcance. Llamen a dos amigos y ofrézcanles pasar hoy, aunque sea por poco rato. Una visita breve también enseña.'],
    ['Terminen la semana enseñando',
     'Todavía pueden llegar a su meta de lecciones con amigos. Aprovechen el fin de semana, cuando muchas familias están en casa. Vayan con una escritura ya preparada.']
  ],
  pmf_lessons: [
    ['Una visita a una familia',
     'Es viernes y su meta con familias en las que no todos son miembros sigue abierta. Escojan un hogar y ofrezcan pasar hoy con un mensaje corto. Su visita puede ser la respuesta a una oración.'],
    ['Un mensaje para todo el hogar',
     'Todavía pueden alcanzar su meta de lecciones con familias parciales. Preparen un mensaje breve que sirva por igual para los niños y los adultos. Así todos se sienten incluidos.']
  ],
  rc_lessons: [
    ['Una visita que fortalece',
     'Es viernes y aún pueden llegar a su meta con conversos recientes. Pasen hoy a saludar a uno de ellos y compartan una escritura. Su visita les recordará que no están solos.'],
    ['No los dejen solos',
     'Su meta de lecciones con conversos recientes sigue abierta esta semana. Escojan a dos de ellos y ofrézcanles una visita corta antes del domingo. El acompañamiento constante es lo que sostiene la fe.']
  ],
  rc_lessons_mcp: [
    ['Abran Mi Senda de los Convenios hoy',
     'Es viernes y su meta con Mi Senda de los Convenios sigue abierta. En su próxima visita a un converso reciente, abran una sección y enséñenla. Bastan quince minutos.'],
    ['Un paso más en la senda',
     'Todavía pueden alcanzar su meta de esta semana con Mi Senda de los Convenios. Escojan a un converso reciente y avancen hoy con él una sección. Cada paso fortalece su convenio.']
  ],
  friend_texts: [
    ['Dos mensajes antes de salir',
     'Es viernes y su meta de mensajes sigue abierta. Antes de salir hoy, escriban a dos amigos para recordarles la reunión del domingo. Un mensaje puede traer a alguien a la Iglesia.'],
    ['Un saludo que llega lejos',
     'Todavía pueden alcanzar su meta de mensajes de esta semana. Escriban a los amigos que hace días no ven y pregúntenles cómo están. A veces solo esperan que alguien pregunte.']
  ],
  friend_calls: [
    ['Tres llamadas hoy',
     'Es viernes y su meta de llamadas todavía se puede alcanzar. Hagan tres llamadas antes de salir e inviten a cada persona a la reunión del domingo. Es una invitación sencilla y directa.'],
    ['Escuchen su voz',
     'Su meta de llamadas sigue abierta esta semana. Llamen hoy a los amigos que más les preocupan y pregunten cómo va su lectura. Escuchar su voz les dirá mucho.']
  ],
  member_contacts: [
    ['Visiten a un miembro hoy',
     'Es viernes y su meta de contactos con miembros sigue abierta. Pasen hoy a saludar a dos familias del barrio y pregúntenles a quién podrían enseñar. Muchas referencias nacen así.'],
    ['Un barrio que ayuda',
     'Todavía pueden alcanzar su meta de contactos con miembros. Llamen a las familias que aún no conocen y preséntense. Cada nueva amistad en el barrio fortalece la obra.']
  ],
  lessons_member_present: [
    ['Llamen a un miembro hoy',
     'Es viernes y su meta de lecciones con un miembro presente sigue abierta. Llamen a un miembro e invítenlo a su próxima cita. Basta con que llegue y comparta su testimonio.'],
    ['Alguien que les acompañe',
     'Todavía pueden alcanzar su meta de lecciones con un miembro presente. Al organizar las citas del fin de semana, inviten a un miembro a cada una. El amigo lo va a agradecer.']
  ],
  references_asked: [
    ['Una pregunta en cada visita',
     'Es viernes y su meta de referencias sigue abierta. En cada visita de hoy, hagan la pregunta antes de despedirse. Una sola referencia puede cambiar la semana entera.'],
    ['¿A quién más podríamos visitar?',
     'Todavía pueden alcanzar su meta de referencias de esta semana. Lleven esa pregunta preparada y háganla con naturalidad. La gente responde cuando se le pregunta con cariño.']
  ],
  member_referrals_received: [
    ['Pidan una referencia hoy',
     'Es viernes y su meta de referencias de miembros sigue abierta. Llamen a dos familias del barrio y pídanles el nombre de una persona. Muchas veces solo falta preguntar.'],
    ['Una conversación con el barrio',
     'Todavía pueden alcanzar su meta de referencias recibidas. Visiten hoy al líder misional del barrio y planifiquen juntos a quién invitar. El trabajo compartido rinde más.']
  ],
  bom_shared: [
    ['Un libro en manos de alguien',
     'Es viernes y su meta de Libros de Mormón sigue abierta. Entreguen hoy al menos un ejemplar con su testimonio y una invitación a leer. Ese libro seguirá enseñando toda la semana.'],
    ['Compártanlo hoy',
     'Todavía pueden alcanzar su meta de ejemplares entregados. Marquen su pasaje favorito y entreguen el libro a alguien que necesite ánimo. El libro hará el resto.']
  ],
  church_invites: [
    ['Inviten para este domingo',
     'Es viernes y su meta de invitaciones a la Iglesia sigue abierta. Inviten hoy a cada persona que visiten y ofrézcanse a pasar por ella. El domingo está a la vuelta de la esquina.'],
    ['Alguien puede venir el domingo',
     'Todavía pueden alcanzar su meta de invitaciones a la Iglesia. Llamen a sus amigos esta tarde y recuérdenles la hora de la reunión. Una llamada trae a más personas de lo que parece.']
  ],
  baptism_doctrine_lessons: [
    ['Una lección sobre el bautismo',
     'Es viernes y su meta sobre la doctrina del bautismo sigue abierta. En su próxima cita, dediquen unos minutos a enseñarla con una escritura. La claridad prepara el corazón.'],
    ['Expliquen el convenio',
     'Todavía pueden alcanzar su meta de lecciones sobre la doctrina del bautismo. Escojan a un amigo y enséñenle hoy qué promete Dios y qué promete él. Es una conversación que cambia todo.']
  ],
  baptismal_invitations: [
    ['Inviten a alguien hoy',
     'Es viernes y su meta de invitaciones al bautismo sigue abierta. Escojan a una persona y extiéndanle hoy la invitación. El Señor prepara el corazón antes de que ustedes lleguen.'],
    ['Una invitación pendiente',
     'Todavía pueden alcanzar su meta de invitaciones bautismales. Piensen en el amigo que ya siente el Espíritu e invítenlo hoy mismo. Puede estar esperando que alguien se lo pida.']
  ],
  baptismal_calendars: [
    ['Un calendario para un amigo',
     'Es viernes y su meta de calendarios bautismales sigue abierta. Lleven uno a su próxima cita y complétenlo junto con la persona. Es una manera sencilla de avanzar.'],
    ['Planifiquen juntos',
     'Todavía pueden alcanzar su meta de calendarios entregados. Escojan a un amigo que ya se está preparando y planifiquen con él las próximas semanas. Un camino claro da confianza.']
  ]
};

// =============================================================================
// MISSED_DAYS — sent by CCSM_Agent3.gs when an area skips nightly reports.
// Selected by Category alone (a3_loadMissedDayMessages), so these rows carry
// no Metric. Tone is deliberately concerned-for-you, never accusatory.
// =============================================================================
var CSC_MISSED_DAYS = [
  ['Les echamos de menos en el informe nocturno',
   'Notamos que faltan algunos informes nocturnos de su área en los últimos días. El informe toma menos de dos minutos y ayuda a sus líderes a saber cómo apoyarles mejor. Si tuvieron algún problema con el formulario, avísennos y les ayudamos.'],
  ['Un recordatorio amable',
   'Su área tiene algunos días sin informe nocturno. Enviarlo cada noche, antes de dormir, hace que no se acumule ni se olvide. Gracias por todo el trabajo de esta semana.'],
  ['¿Cómo están por allá?',
   'Hemos echado de menos varios informes nocturnos de su área. Si algo les ha impedido enviarlos, escríbannos y con gusto les ayudamos. Nos interesa mucho más cómo están ustedes que el informe mismo.']
];

// =============================================================================
// ROW BUILDERS
// =============================================================================

/**
 * Zero-pads to 2 digits. Forked from populateMessageBankStructure.gs:40.
 */
function csc_pad2_(n) { return (n < 10 ? '0' : '') + String(n); }

/**
 * Returns the metric keys the content matrix must cover, read from the live
 * definitions rather than restated here: the 5 A1A_RATE_METRICS keys, then
 * the 20 NUMBER-typed CCSM_NIGHTLY_QUESTIONS keys.
 */
function csc_rateMetricKeys_() {
  return A1A_RATE_METRICS.map(function(m) { return m.key; });
}

function csc_countMetricKeys_() {
  return CCSM_NIGHTLY_QUESTIONS
    .filter(function(q) { return q.type === 'NUMBER'; })
    .map(function(q) { return q.key; });
}

/**
 * Assembles one MESSAGE_BANK row in CCSM_TAB_SPECS column order.
 * Scripture_Text is '' unless CSC_ROW_OVERRIDES supplies verified wording.
 */
function csc_makeRow_(messageId, category, metricKey, subject, body) {
  var meta = CSC_METRIC_META[metricKey] || { chapter: '', pmgDesc: '', scripture: '' };
  var o    = CSC_ROW_OVERRIDES[messageId] || {};
  return [
    messageId,
    category,
    metricKey || '',
    '',                                                        // Subcategory — unused by every CCSM agent
    subject,
    body,
    o.pmgChapter     !== undefined ? o.pmgChapter     : meta.chapter,
    o.pmgDescription !== undefined ? o.pmgDescription : meta.pmgDesc,
    o.scripture      !== undefined ? o.scripture      : meta.scripture,
    o.scriptureText  !== undefined ? o.scriptureText  : '',    // see content rule 1
    'TRUE'
  ];
}

/**
 * Builds all 193 MESSAGE_BANK data rows (no header).
 * Throws if any metric key is missing content — a silently short bank means
 * pickMessage() returns null and an area gets no coaching message at all.
 */
function csc_buildMessageRows_() {
  var rateKeys  = csc_rateMetricKeys_();
  var countKeys = csc_countMetricKeys_();
  var allKeys   = rateKeys.concat(countKeys);
  var rows      = [];

  allKeys.forEach(function(key) {
    var meta = CSC_METRIC_META[key];
    if (!meta) throw new Error('CCSM_SeedContent: no CSC_METRIC_META entry for metric "' + key + '".');

    var strength = CSC_STRENGTH[key];
    var growth   = CSC_GROWTH[key];
    if (!strength || strength.length !== 3) throw new Error('CCSM_SeedContent: expected 3 strength messages for "' + key + '".');
    if (!growth   || growth.length   !== 3) throw new Error('CCSM_SeedContent: expected 3 growth messages for "' + key + '".');

    strength.forEach(function(m, i) {
      rows.push(csc_makeRow_('MSG-CS-' + meta.slug + '-' + csc_pad2_(i + 1),
        'SUNDAY_COACHING_STRENGTH', key, m[0], m[1]));
    });
    growth.forEach(function(m, i) {
      rows.push(csc_makeRow_('MSG-CG-' + meta.slug + '-' + csc_pad2_(i + 1),
        'SUNDAY_COACHING_GROWTH', key, m[0], m[1]));
    });
  });

  countKeys.forEach(function(key) {
    var meta   = CSC_METRIC_META[key];
    var friday = CSC_FRIDAY[key];
    if (!friday || friday.length !== 2) throw new Error('CCSM_SeedContent: expected 2 Friday messages for "' + key + '".');
    friday.forEach(function(m, i) {
      rows.push(csc_makeRow_('MSG-FE-' + meta.slug + '-' + csc_pad2_(i + 1),
        'FRIDAY_ENCOURAGEMENT', key, m[0], m[1]));
    });
  });

  CSC_MISSED_DAYS.forEach(function(m, i) {
    rows.push(csc_makeRow_('MSG-MD-' + csc_pad2_(i + 1), 'MISSED_DAYS', '', m[0], m[1]));
  });

  return rows;
}

/**
 * Builds the 10 starter KNOWLEDGE_BASE rows read by CCSM_AgentQA.gs.
 * Key-indicator wording is taken from WeeklyReportForm_ES.gs KEY_INDICATORS
 * (:66-74) so a missionary searching the exact form label finds the answer.
 * The support address comes from AGENT_CONFIG — never hardcoded.
 */
function csc_buildKnowledgeRows_() {
  var support = getConfig('SEND_FROM_EMAIL') || getConfig('TEST_INBOX_EMAIL') || '';
  var today   = Utilities.formatDate(new Date(), getMissionTimezone(), 'yyyy-MM-dd');
  var ki      = 'Indicadores Clave';

  var rows = [
    ['KB-001', 'Informes', '¿Cómo envío el informe nocturno?',
     'Cada noche, antes de dormir, abra el enlace del Informe Nocturno Misional que le enviaron sus líderes. Elija su zona y su área, indique la fecha del día que está informando y complete cada pregunta con los números de ese día. Envíe el formulario una sola vez por compañerismo y por día.',
     'informe nocturno, formulario diario, enviar informe, reporte de la noche'],
    ['KB-002', 'Informes', '¿Cómo envío el informe semanal?',
     'El Informe Semanal Misional se envía una vez por semana, al terminar la planificación semanal. Elija su zona y su área, e ingrese los resultados reales de la semana que terminó junto con las metas que fijó para la semana siguiente. Use los mismos números que registró en la aplicación Predicad Mi Evangelio.',
     'informe semanal, planificación semanal, metas, indicadores clave'],
    ['KB-003', ki, '¿Qué significa "Nuevas personas encontradas"?',
     'Son las personas nuevas a quienes usted comenzó a enseñar durante la semana. Cada persona se cuenta una sola vez, en la semana en que recibió su primera lección. Ingrese el mismo número que registró en la aplicación Predicad Mi Evangelio.',
     'nuevas personas, encontradas, indicador clave, hallar'],
    ['KB-004', ki, '¿Qué significa "Lecciones con miembros"?',
     'Son las lecciones que usted enseñó con un miembro de la Iglesia presente. La presencia de un miembro ayuda a que el amigo tenga una amistad en el barrio desde el comienzo. Registre el total de la semana, tal como aparece en la aplicación Predicad Mi Evangelio.',
     'lecciones con miembros, miembro presente, indicador clave'],
    ['KB-005', ki, '¿Qué significa "Amigos en la reunión sacramental"?',
     'Es el número de amigos de la Iglesia que asistieron a la reunión sacramental durante la semana. Cuente a cada persona una sola vez por semana. Ingrese el mismo número que registró en la aplicación Predicad Mi Evangelio.',
     'reunión sacramental, asistencia, amigos, indicador clave'],
    ['KB-006', ki, '¿Qué significa "Amigos en la Iglesia durante su primera semana de enseñanza"?',
     'Es el número de amigos que asistieron a la Iglesia dentro de la primera semana desde que recibieron su primera lección. Este indicador ayuda a ver con qué rapidez los nuevos amigos son invitados a adorar. Registre únicamente a quienes cumplen esa condición.',
     'primera semana, asistencia, amigos nuevos, indicador clave'],
    ['KB-007', ki, '¿Qué significa "Amigos con fecha bautismal"?',
     'Es el número de amigos que tienen una fecha bautismal establecida durante esa semana. Se cuenta a la persona mientras su fecha siga vigente. Ingrese el mismo número que registró en la aplicación Predicad Mi Evangelio.',
     'fecha bautismal, bautismo, indicador clave'],
    ['KB-008', ki, '¿Qué significa "Bautizados y confirmados"?',
     'Es el número de personas que se bautizaron y fueron confirmadas miembros de la Iglesia durante la semana. Ingrese el mismo número que registró en la aplicación Predicad Mi Evangelio. Si tiene dudas sobre cómo registrar un caso particular, consulte con sus líderes de zona.',
     'bautizados, confirmados, ordenanzas, indicador clave'],
    ['KB-009', ki, '¿Qué significa "Conversos recientes en la Iglesia"?',
     'Es el número de conversos recientes de su área que asistieron a las reuniones de la Iglesia durante la semana. Cuente a cada persona una sola vez por semana. Ingrese el mismo número que registró en la aplicación Predicad Mi Evangelio.',
     'conversos recientes, retención, asistencia, indicador clave'],
    ['KB-010', 'Ayuda', '¿A quién escribo si tengo un problema con el formulario o con los informes?',
     'Escriba a ' + support + ' y describa el problema con el mayor detalle posible. Indique su zona, su área y la fecha del informe que intentaba enviar. Le responderemos lo antes posible.',
     'ayuda, soporte, problema, contacto, error']
  ];

  return rows.map(function(r) {
    return [r[0], r[1], r[2], r[3], r[4], 'PMG Compass CCSM', today, 0];
  });
}

// =============================================================================
// WRITERS
// =============================================================================

/**
 * Rewrites `tabName` with `headers` + `rows`, in batches of 50 with a 500 ms
 * pause between them (Provo pattern — populateMessageBankStructure.gs:5-6 —
 * to keep a large write inside the Apps Script execution limit).
 *
 * Verification RE-OPENS the spreadsheet by ID. An in-place read of a range
 * you just wrote returns the local pending value, not true server state, so a
 * naive read-back would "verify" a write that never landed.
 */
function csc_writeTab_(tabName, headers, rows) {
  var sheet = getTab(tabName);
  // The tab's OWN parent, not getSpreadsheet() — MESSAGE_BANK/
  // LEADERSHIP_MESSAGE_BANK can live in a different spreadsheet from the
  // bound one once split (see CCSM_Helpers.gs ccsmSpreadsheetForTab_()), and
  // getSpreadsheet() would silently verify against the wrong file for those.
  var ssId = sheet.getParent().getId();

  sheet.clearContents();
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);

  var BATCH = 50;
  for (var i = 0; i < rows.length; i += BATCH) {
    var chunk = rows.slice(i, i + BATCH);
    sheet.getRange(2 + i, 1, chunk.length, headers.length).setValues(chunk);
    if (i + BATCH < rows.length) Utilities.sleep(500);
  }
  SpreadsheetApp.flush();

  // True server-state verification — fresh handle, fresh read.
  var verifySheet = SpreadsheetApp.openById(ssId).getSheetByName(tabName);
  var actual      = verifySheet.getLastRow() - 1;
  if (actual !== rows.length) {
    throw new Error('CCSM_SeedContent: ' + tabName + ' verification failed — expected ' +
      rows.length + ' data rows, found ' + actual + '.');
  }
  Logger.log('CCSM_SeedContent: ' + tabName + ' written and verified — ' + actual + ' rows.');
  return actual;
}

/**
 * Seeds MESSAGE_BANK with the full Spanish content set (193 rows).
 * Zero-argument so it can be run straight from the Apps Script Run button.
 * ⚠️ INITIAL SETUP ONLY — like seedCcsmLeadershipMessageBank(), this rewrites
 * the tab from scratch. MESSAGE_BANK is mission-editable content, the same as
 * LEADERSHIP_MESSAGE_BANK: once real coaching emails are going out and
 * mission leadership may have hand-edited rows in the sheet, do NOT re-run
 * this — it would silently wipe those edits back to the original seeded
 * text. Run it once, on an empty tab, to populate the starting content; after
 * that, edit MESSAGE_BANK directly in the sheet.
 */
function seedCcsmMessageBank() {
  var spec = null;
  CCSM_TAB_SPECS.forEach(function(t) { if (t.name === 'MESSAGE_BANK') spec = t; });
  if (!spec) throw new Error('CCSM_SeedContent: MESSAGE_BANK is not defined in CCSM_TAB_SPECS.');
  return csc_writeTab_('MESSAGE_BANK', spec.headers, csc_buildMessageRows_());
}

/**
 * Seeds KNOWLEDGE_BASE with 10 starter Spanish Q&A rows for CCSM_AgentQA.gs.
 * Zero-argument; safe to re-run.
 */
function seedCcsmKnowledgeBase() {
  var spec = null;
  CCSM_TAB_SPECS.forEach(function(t) { if (t.name === 'KNOWLEDGE_BASE') spec = t; });
  if (!spec) throw new Error('CCSM_SeedContent: KNOWLEDGE_BASE is not defined in CCSM_TAB_SPECS.');
  return csc_writeTab_('KNOWLEDGE_BASE', spec.headers, csc_buildKnowledgeRows_());
}

/**
 * Assembles one LEADERSHIP_MESSAGE_BANK row in CCSM_TAB_SPECS column order.
 */
function csc_makeLeadershipRow_(messageId, theme, subject, body, pmgPage, scripture, scriptureText) {
  return [messageId, theme, subject, body, pmgPage || '', scripture || '', scriptureText || '', 'TRUE'];
}

/**
 * Builds the 10 LEADERSHIP_MESSAGE_BANK data rows (no header) — the same 10
 * messages that used to be the hardcoded `_LEADERSHIP_MSGS` array in
 * CCSM_Agent1C.gs, transcribed verbatim. PMG_Page/Scripture/Scripture_Text
 * are unverified citation content (see CONTENT_REVIEW.md) — CCSM_Agent1C.gs
 * withholds them at render time regardless of what this seeds.
 */
function csc_buildLeadershipMessageRows_() {
  return [
    // ── BUSCAR (Finding) ──────────────────────────────────────────────────
    csc_makeLeadershipRow_('LM-01', 'Buscar', 'Cada Contacto Es una Conversación en Potencia',
      'Los números muestran cuántos contactos se intentaron — pero la pregunta que vale la pena hacer es qué pasó después. Esta semana en el inventario de compañerismo, anime a sus líderes de distrito a averiguar: de cada contacto realizado, ¿cuántos se convirtieron en una conversación real, y cuántos en una cita de regreso confirmada? Una conversación genuina con una próxima visita concreta es la unidad de trabajo que mueve a las personas hacia el bautismo.',
      '157', 'D. y C. 4:4-5',
      'Por tanto, oh vosotros que os embarcáis al servicio de Dios, ved que le sirváis con todo vuestro corazón, alma, mente y fuerza.'),
    csc_makeLeadershipRow_('LM-02', 'Buscar', 'Las Referencias Necesitan una Respuesta el Mismo Día',
      'Cada referencia que recibe su zona tiene una ventana de oportunidad. Cuando un miembro entrega el nombre de un amigo, un intento de contacto el mismo día no es solo una buena práctica — es una declaración a ese miembro de que se toma en serio su confianza. Revise esta semana: ¿recibió cada referencia un intento de contacto dentro de 24 horas? Conviértalo en un estándar de zona y reconozca a los misioneros que lo hacen sin que se les recuerde.',
      '164', 'D. y C. 88:81',
      'He aquí, os envié a testificar y amonestar al pueblo, y le corresponde a todo hombre que ha sido amonestado amonestar a su prójimo.'),
    // ── ENSEÑAR (Teaching) ────────────────────────────────────────────────
    csc_makeLeadershipRow_('LM-03', 'Enseñar', 'Una Lección Más Cambia la Trayectoria',
      'Los amigos que reciben más de una lección por semana progresan a un ritmo notablemente más rápido. Mire los números de enseñanza de su zona y pregunte a sus líderes de distrito: ¿a qué amigos se les está viendo dos veces por semana, y cuáles llevan diez días sin una lección? Anime a sus misioneros a planificar dos visitas por amigo como norma, no como excepción.',
      '174', 'Alma 26:22',
      'Sí, aquel que se arrepiente y ejerce la fe, y produce buenas obras, y ora continuamente sin cesar — a tal se le concede conocer los misterios de Dios.'),
    csc_makeLeadershipRow_('LM-04', 'Enseñar', 'Las Lecciones con Miembro Presente Son el Estándar',
      'Un amigo que llega al bautismo sin haber estado nunca en una sala con un miembro del barrio es un amigo en riesgo. Esta semana, pida a cada compañerismo que identifique un miembro que llevarán a una lección antes del domingo — no necesita ser alguien del consejo de barrio, solo una persona amigable de la Iglesia que pueda sentarse con un nuevo amigo.',
      '85', 'D. y C. 11:21',
      'Escudriña las Escrituras; procura obtener sabiduría; asocíate con lo bueno, con lo que edifica.'),
    // ── INDICADORES CLAVE (Key Indicators) ────────────────────────────────
    csc_makeLeadershipRow_('LM-05', 'Indicadores Clave', 'Una Fecha Bautismal Es una Promesa, No una Fecha Límite',
      'Fijar una fecha no es presión — es el regalo de una meta. Cuando un amigo se compromete con una fecha bautismal, cada cita posterior, cada visita a la reunión sacramental, cada presentación con un miembro cobra más sentido. Mire las invitaciones al bautismo de su zona y pregunte a sus líderes: ¿cómo se extendieron esas invitaciones? ¿Fueron pedidas con fe, ligadas al testimonio que el amigo ya está desarrollando?',
      '205', 'Moroni 10:4',
      'Y cuando recibáis estas cosas, quisiera exhortaros a que preguntaseis a Dios, el Padre Eterno, en el nombre de Cristo, si no son verdaderas estas cosas.'),
    csc_makeLeadershipRow_('LM-06', 'Indicadores Clave', 'Pida un Compromiso Cada Vez',
      'Toda lección debería terminar con un compromiso claro y específico — no una invitación vaga a pensarlo, sino una petición real con una respuesta. Practique en su próxima reunión de zona o distrito: ¿pueden sus misioneros pedir una fecha bautismal con naturalidad, sin dudar, sin disculparse por la pregunta? Un misionero que no pregunta priva a sus amigos de la oportunidad de decir que sí.',
      '205', '2 Nefi 31:17',
      'Por tanto, haced las cosas que os he dicho que he visto que haría vuestro Señor y vuestro Redentor.'),
    // ── CULTURA DE ZONA (Zone Culture) ────────────────────────────────────
    csc_makeLeadershipRow_('LM-07', 'Cultura de Zona', 'El Informe Nocturno Es Rendir Cuentas al Señor',
      'La constancia en el informe refleja la cultura de la zona. Cuando los misioneros informan cada noche, rinden cuentas al Señor, a usted y entre ellos — no solo llenan un formulario. Revise el patrón de informes de esta semana y aborde con amor cualquier área inconstante, ayudando a los misioneros a entender que un informe nocturno honesto es parte de su convenio de servir con integridad.',
      '', 'D. y C. 59:21',
      'Y en nada ofende el hombre a Dios, ni se enciende su ira, sino contra aquellos que no confiesan su mano en todas las cosas, ni obedecen sus mandamientos.'),
    csc_makeLeadershipRow_('LM-08', 'Cultura de Zona', 'Reconozca a Sus Misioneros por lo que Hacen Bien',
      'Esta semana, encuentre algo específico que cada compañerismo de su zona está haciendo bien — y dígalo en voz alta. No un ánimo genérico, sino un reconocimiento concreto: "Contactaron esa referencia el mismo día que llegó. Ese es el estándar." Los misioneros que se sienten genuinamente vistos por sus líderes trabajan con más ánimo y se mantienen espiritualmente más fuertes.',
      '', 'D. y C. 121:41',
      'Ningún poder o influencia puede o debe mantenerse en virtud del sacerdocio, sino por medio de la persuasión, de la longanimidad, de la benignidad y la mansedumbre, y del amor sincero.'),
    // ── FE (Faith) ─────────────────────────────────────────────────────────
    csc_makeLeadershipRow_('LM-09', 'Fe', 'Su Zona Sigue Su Fe',
      'El tono espiritual de su zona lo marca usted. Cuando testifica con sencillez, cuando habla de sus amigos con amor genuino en lugar de tratarlos como un número, cuando modela lo que significa trabajar con esfuerzo y confiar en Dios con los resultados — sus misioneros lo absorben y lo llevan a sus áreas. Esta semana, pregúntese con honestidad: ¿qué cree posible mi zona? Luego enséñeles a creer un poco más.',
      '', 'Alma 26:12',
      'Sé que no soy nada; en cuanto a mi propia fuerza, soy débil; por tanto, no me jactaré de mí mismo, sino que me jactaré de mi Dios, porque en su fuerza puedo hacer todas las cosas.'),
    csc_makeLeadershipRow_('LM-10', 'Fe', 'La Obra Es de Él',
      'Cada amigo que se enseña en su zona es un hijo de Dios que el Señor ha estado preparando desde mucho antes de que sus misioneros tocaran su puerta. Su labor no es fabricar la conversión — es presentarse, enseñar con el Espíritu, extender invitaciones con fe, y dejar el resultado en manos de Él. Si los números de esta semana no son los que esperaba, llévelo al Señor en oración y pregunte qué ve Él que usted no ve.',
      '', 'D. y C. 18:15',
      'Y si sucede que trabajáis todos vuestros días clamando arrepentimiento a este pueblo, y me traéis, aunque sea una sola alma, ¡cuán grande será vuestro gozo!')
  ];
}

/**
 * Seeds LEADERSHIP_MESSAGE_BANK with the 10 leadership coaching messages.
 * ⚠️ ONE-TIME MIGRATION ONLY — unlike seedCcsmMessageBank/seedCcsmKnowledgeBase,
 * do NOT re-run this after mission leadership (AP/president) starts editing
 * the tab directly: it rewrites the tab from scratch and would silently wipe
 * their edits. Deliberately NOT called from seedCcsmContent() for that
 * reason. Run it once, by itself, to migrate off the old hardcoded
 * CCSM_Agent1C.gs array; after that, edit the tab directly — no more code
 * deploys needed for wording changes.
 */
function seedCcsmLeadershipMessageBank() {
  var spec = null;
  CCSM_TAB_SPECS.forEach(function(t) { if (t.name === 'LEADERSHIP_MESSAGE_BANK') spec = t; });
  if (!spec) throw new Error('CCSM_SeedContent: LEADERSHIP_MESSAGE_BANK is not defined in CCSM_TAB_SPECS.');
  return csc_writeTab_('LEADERSHIP_MESSAGE_BANK', spec.headers, csc_buildLeadershipMessageRows_());
}

/**
 * ONE-TIME MIGRATION: creates a brand-new spreadsheet named "CCSM Mission
 * Trainings" holding only MESSAGE_BANK and LEADERSHIP_MESSAGE_BANK, copied
 * verbatim from wherever they currently live (their live content — including
 * any hand edits — not the code's original seed text).
 *
 * WHY THIS EXISTS: Google ties "can edit this spreadsheet" to "can open its
 * bound Apps Script project" — sharing Editor access to COMPASS_CCSM so
 * mission leadership can edit these two tabs also hands them every .gs file
 * and Script Properties (including GEMINI_API_KEY). This gives them their own
 * spreadsheet, with no script attached, to edit instead.
 *
 * Skips a source tab that doesn't exist yet (e.g. LEADERSHIP_MESSAGE_BANK
 * before its own seeder has been run once) rather than failing outright —
 * logs which ones it copied.
 *
 * AFTER RUNNING:
 *   1. Copy the logged spreadsheet ID into a new MESSAGE_BANK_SPREADSHEET_ID
 *      row in AGENT_CONFIG. From then on getTab() (CCSM_Helpers.gs) resolves
 *      both tab names to the NEW spreadsheet automatically — nothing else to
 *      change in code.
 *   2. Confirm it actually reads from the new location — smokeTestPipeline()
 *      or previewOneCoachingEmail() both go through getTab().
 *   3. THEN delete the old MESSAGE_BANK / LEADERSHIP_MESSAGE_BANK tabs from
 *      COMPASS_CCSM by hand, so nobody edits the now-inert local copy by
 *      mistake. Not automatic — do this only after step 2 confirms the split
 *      is really live.
 *   4. Share the NEW spreadsheet (Editor) with mission leadership. Never
 *      share COMPASS_CCSM itself for this purpose.
 *
 * Do not run this more than once on purpose — it always creates ANOTHER new
 * spreadsheet rather than reusing one. If you do by accident, delete the
 * extra file; it never touches the source tabs, so nothing is lost either way.
 */
function splitMessageBanksToOwnSpreadsheet() {
  var newSs = SpreadsheetApp.create('CCSM Mission Trainings');
  var copied = [];

  ['MESSAGE_BANK', 'LEADERSHIP_MESSAGE_BANK'].forEach(function(tabName) {
    var sourceSheet;
    try {
      // Reads from wherever the tab lives TODAY — the bound sheet, since this
      // function is how the split itself happens.
      sourceSheet = getTab(tabName);
    } catch (e) {
      Logger.log('splitMessageBanksToOwnSpreadsheet: skipping ' + tabName + ' — ' + e.message);
      return;
    }
    var values = sourceSheet.getDataRange().getValues();
    var dest = newSs.insertSheet(tabName);
    if (values.length) {
      dest.getRange(1, 1, values.length, values[0].length).setValues(values);
      dest.getRange(1, 1, 1, values[0].length).setFontWeight('bold').setBackground('#173A72').setFontColor('#FFFFFF');
      dest.setFrozenRows(1);
    }
    copied.push(tabName);
  });

  var def = newSs.getSheetByName('Sheet1') || newSs.getSheetByName('Hoja 1');
  if (def) newSs.deleteSheet(def);
  SpreadsheetApp.flush();

  Logger.log('CCSM_SeedContent: copied ' + copied.join(', ') + ' into a new spreadsheet.');
  Logger.log('New spreadsheet: ' + newSs.getUrl());
  Logger.log('Spreadsheet ID: ' + newSs.getId());
  Logger.log('NEXT STEPS: (1) add MESSAGE_BANK_SPREADSHEET_ID = ' + newSs.getId() + ' to AGENT_CONFIG; ' +
             '(2) confirm with smokeTestPipeline() or previewOneCoachingEmail(); ' +
             '(3) delete the old MESSAGE_BANK/LEADERSHIP_MESSAGE_BANK tabs from COMPASS_CCSM; ' +
             '(4) share the NEW spreadsheet (Editor) with mission leadership — never COMPASS_CCSM itself.');
  return newSs.getId();
}

/**
 * Cosmetic only — touches no data. Makes LEADERSHIP_MESSAGE_BANK's column
 * widths/wrap match MESSAGE_BANK's own style (splitMessageBanksToOwnSpreadsheet
 * gives both tabs the same header styling, but never sets column widths or
 * wrap — MESSAGE_BANK only looks right today because it was re-pasted by hand
 * afterward, which carries formatting; a fresh seed like LEADERSHIP_MESSAGE_BANK
 * does not). Safe to run more than once. Run this AFTER
 * splitMessageBanksToOwnSpreadsheet() and seedCcsmLeadershipMessageBank(), since
 * it reads through the same getTab() redirect they use.
 */
function formatLeadershipMessageBankSheet() {
  var sheet = getTab('LEADERSHIP_MESSAGE_BANK');
  var lastCol = sheet.getLastColumn();
  var lastRow = sheet.getLastRow();
  var headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];

  sheet.getRange(1, 1, 1, lastCol)
    .setFontWeight('bold')
    .setBackground('#173A72')
    .setFontColor('#FFFFFF')
    .setFontFamily('Arial')
    .setFontSize(10);
  sheet.setFrozenRows(1);

  sheet.setColumnWidths(1, lastCol, 100);

  var bodyCol = headers.indexOf('Body_Text') + 1;
  if (bodyCol > 0) {
    sheet.setColumnWidth(bodyCol, 403);
    if (lastRow > 1) {
      sheet.getRange(2, bodyCol, lastRow - 1, 1).setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
    }
  }

  var activeCol = headers.indexOf('Active') + 1;
  if (activeCol > 0 && lastRow > 1) {
    sheet.getRange(2, activeCol, lastRow - 1, 1).setHorizontalAlignment('center');
  }

  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, lastCol).setFontFamily('Arial').setFontSize(10);
  }

  Logger.log('formatLeadershipMessageBankSheet: styled ' + lastCol + ' columns x ' + lastRow + ' rows.');
}

/**
 * Convenience: seeds KNOWLEDGE_BASE (the one tab still meant to be reseeded
 * from code as its content changes). MESSAGE_BANK and LEADERSHIP_MESSAGE_BANK
 * are deliberately excluded — both are mission-editable directly in the
 * sheet once seeded once; see seedCcsmMessageBank()'s and
 * seedCcsmLeadershipMessageBank()'s own comments. Run either of those
 * separately, once, during initial setup only.
 */
function seedCcsmContent() {
  seedCcsmKnowledgeBase();
}
