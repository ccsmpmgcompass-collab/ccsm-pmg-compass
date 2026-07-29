"""English source string -> Spanish (es_CL). Populated by Tasks 9-12.

Keys are the exact English strings as they appear in the UI. A key that is
absent falls back to English, so this dict is always safe to be incomplete.

Register: formal (usted), as appropriate for mission leadership.

A handful of entries map a string to itself. Those are deliberate, not
oversights - "PMG Compass" is the product name, and abbreviations that are
already the mission's shared vocabulary are left as they are.
"""

# Kept as a named constant so the key matches the extractor byte for byte: it
# records strings stripped, and this block reaches t() with its surrounding
# newlines intact.
_APP_GUIDE_EN = """**Overview & assistant**
- **Home** — Mission Assistant. Ask natural-language questions about mission data, procedures, or performance.
- **Dashboard** — Mission pulse: weekly KPIs, submission compliance (with per-area detail), zone summary, and trend charts.
- **Goals** — Every area's progress against weekly and transfer goals, color-coded.

**Drill down (mission → zone → district → area)**
- **Breakdowns** — Zone, district, or area in one place: pick a zone for period comparisons and pipeline data, add a district to drill in, or pick an area for the single-area view (compliance calendar, anomaly flags, notes).

**Performance & analysis**
- **Scores** — Weekly composite Effort / Skill / KI / Effectiveness scores per area, with a configurable weight editor. Also has Daily Activity (day-by-day nightly-form explorer) and Analyze (anomaly detection + next-week projections) tabs.
- **Finding Funnel** — Upload Tableau exports to see the finding-to-baptism pipeline and area rankings.

**Operations**
- **Notes** — Area notes with tags, search, and email follow-up reminders.
- **Maintenance** — System health, weekly to-do, knowledge base, agent settings, and form-question configuration."""

_APP_GUIDE_ES = """**Vista general y asistente**
- **Inicio** — Asistente de la Misión. Haga preguntas en lenguaje natural sobre los datos, procedimientos o desempeño de la misión.
- **Panel** — El pulso de la misión: indicadores semanales, cumplimiento de envíos (con detalle por área), resumen por zona y gráficos de tendencia.
- **Metas** — El progreso de cada área frente a las metas semanales y de traslado, con códigos de color.

**Análisis detallado (misión → zona → distrito → área)**
- **Desgloses** — Zona, distrito o área en un solo lugar: elija una zona para comparar períodos y ver el proceso, agregue un distrito para profundizar, o elija un área para la vista individual (calendario de cumplimiento, alertas de anomalías, notas).

**Desempeño y análisis**
- **Puntajes** — Puntajes semanales combinados de Esfuerzo / Habilidad / IC / Efectividad por área, con un editor de pesos configurable. También incluye las pestañas Actividad Diaria (explorador día por día del formulario nocturno) y Analizar (detección de anomalías + proyecciones para la próxima semana).
- **Embudo de Búsqueda** — Cargue las exportaciones de Tableau para ver el proceso desde el hallazgo hasta el bautismo y la clasificación de áreas.

**Operaciones**
- **Notas** — Notas por área con etiquetas, búsqueda y recordatorios de seguimiento por correo.
- **Mantenimiento** — Estado del sistema, tareas semanales, base de conocimiento, configuración de agentes y configuración de preguntas del formulario."""

ES: dict[str, str] = {
    # ── Brand ────────────────────────────────────────────────────────────────
    "PMG Compass": "PMG Compass",

    # ── Home / assistant ─────────────────────────────────────────────────────
    _APP_GUIDE_EN: _APP_GUIDE_ES,
    "App Guide — what each page does":
        "Guía de la Aplicación — qué hace cada página",
    "Mission": "Misión",
    "Mission Assistant": "Asistente de la Misión",
    "{mission} · Welcome back, {name}":
        "{mission} · Bienvenido de nuevo, {name}",
    "Week": "Semana",
    "Last updated": "Última actualización",
    "Loading knowledge base...": "Cargando la base de conocimiento...",
    "Loading mission data...": "Cargando los datos de la misión...",
    "Thinking...": "Pensando...",
    "Reload": "Recargar",
    "Refresh live mission data": "Actualizar los datos en vivo de la misión",
    "Clear": "Borrar",
    "Clear chat history": "Borrar el historial de conversación",
    "Live data unavailable — click **Reload** to retry.":
        "Datos en vivo no disponibles — haga clic en **Recargar** para reintentar.",
    "Try asking:": "Pruebe preguntando:",
    "question": "pregunta",
    "Ask about mission data, procedures, or performance...":
        "Pregunte sobre datos, procedimientos o desempeño de la misión...",
    "Send": "Enviar",
    "GEMINI_API_KEY not configured. Add it to .streamlit/secrets.toml.":
        "GEMINI_API_KEY no está configurada. Agréguela en .streamlit/secrets.toml.",
    "Gemini is rate-limited — please wait a few seconds and try again.":
        "Gemini alcanzó su límite de solicitudes — espere unos segundos e inténtelo de nuevo.",
    "I wasn't able to generate an answer. Please rephrase your question.":
        "No pude generar una respuesta. Por favor reformule su pregunta.",

    # ── Starter questions ────────────────────────────────────────────────────
    "Give me a 30-second briefing on the mission right now":
        "Deme un resumen de 30 segundos sobre la misión en este momento",
    "Which areas need my attention this week?":
        "¿Qué áreas necesitan mi atención esta semana?",
    "Who are the top-performing areas right now?":
        "¿Cuáles son las áreas con mejor desempeño en este momento?",
    "How is our baptism pipeline looking?":
        "¿Cómo va nuestro proceso de bautismos?",
    "Which zone is strongest at finding new people?":
        "¿Qué zona es más fuerte para encontrar nuevas personas?",
    "Who hasn't submitted recently?":
        "¿Quiénes no han enviado su reporte recientemente?",

    # ── Dashboard ────────────────────────────────────────────────────────────
    "{mission} — Executive Dashboard": "{mission} — Panel Ejecutivo",
    "No data for this section yet.": "Aún no hay datos para esta sección.",
    "Summary data refreshes daily at noon. Submission compliance is computed "
    "live. Mission-level only — drill into a zone, district or area on the "
    "Breakdowns page.":
        "Los datos de resumen se actualizan a diario al mediodía. El cumplimiento "
        "de envíos se calcula en vivo. Solo a nivel de misión — profundice en una "
        "zona, distrito o área en la página Desgloses.",
    "Key Indicators": "Indicadores Clave",
    "Key Indicators — Week Ending {week}":
        "Indicadores Clave — Semana que Termina el {week}",
    "Weekly Key Indicators — Last 7 Days":
        "Indicadores Clave Semanales — Últimos 7 Días",
    "Zone Leaderboard — Last 7 Days":
        "Tabla de Posiciones por Zona — Últimos 7 Días",
    "8-Week Trend — Mission Totals":
        "Tendencia de 8 Semanas — Totales de la Misión",
    "Daily NM Lessons — Last 7 Days":
        "Lecciones Diarias a NM — Últimos 7 Días",
    "Daily Effort Breakdown — Last 7 Days":
        "Desglose Diario de Esfuerzo — Últimos 7 Días",
    "All Effort": "Esfuerzo Total",
    "Most Effort": "Esfuerzo Mayoritario",
    "Some Effort": "Algo de Esfuerzo",
    "Areas reporting full effort": "Áreas que reportan esfuerzo total",
    "Areas reporting most effort": "Áreas que reportan esfuerzo mayoritario",
    "Areas reporting some effort": "Áreas que reportan algo de esfuerzo",
    "Effort by area — who reported what (last 7 days)":
        "Esfuerzo por área — quién reportó qué (últimos 7 días)",
    "No per-area effort responses in the last 7 days.":
        "No hay respuestas de esfuerzo por área en los últimos 7 días.",
    "{n} areas · sorted by effort score "
    "(All=3, Most=2, Some=1, averaged per submission). "
    "Counts are submissions per area over the last 7 days.":
        "{n} áreas · ordenadas por puntaje de esfuerzo "
        "(Todo=3, Mayoría=2, Algo=1, promediado por envío). "
        "Los conteos son envíos por área durante los últimos 7 días.",
    "Submission Compliance": "Cumplimiento de Envíos",
    "Nightly Submission Compliance — Daily %":
        "Cumplimiento de Envíos Nocturnos — % Diario",
    "No nightly compliance data yet.":
        "Aún no hay datos de cumplimiento nocturno.",
    "Weekly Report Submission — By Week":
        "Envío del Reporte Semanal — Por Semana",
    "No weekly submission data yet.":
        "Aún no hay datos de envíos semanales.",
    "Area Submission Detail — all-time compliance per area":
        "Detalle de Envíos por Área — cumplimiento histórico por área",
    "No per-area submission data available yet.":
        "Aún no hay datos de envíos por área.",
    "No areas match the current filter.":
        "Ninguna área coincide con el filtro actual.",
    "{n} area(s) shown — worst first":
        "{n} área(s) mostradas — las más bajas primero",

    # ── Filters and table headers ────────────────────────────────────────────
    "All Zones": "Todas las Zonas",
    "Show": "Mostrar",
    "All": "Todas",
    "Behind only": "Solo atrasadas",
    "On Track only": "Solo al día",
    "Area": "Área",
    "Zone": "Zona",
    "District": "Distrito",
    "Days Submitted": "Días Enviados",
    "Days Possible": "Días Posibles",
    "Compliance %": "% de Cumplimiento",
    "Last Submitted": "Último Envío",
    "Status": "Estado",

    # Compliance status cell values. These stay English in the DataFrame that
    # the filters run on and are translated only for display, so a language
    # switch can never change which rows are shown.
    "On Track": "Al día",
    "Partial": "Parcial",
    "Behind": "Atrasada",

    # ── Breakdowns ───────────────────────────────────────────────────────────
    "Breakdowns": "Desgloses",
    "{mission} — Zone, District & Area Performance":
        "{mission} — Desempeño por Zona, Distrito y Área",
    "Pick a Zone, District or Area above — type in any box to search. "
    "The deepest selection is what gets broken down: choose a zone for the "
    "zone view, add a district to drill into it, add an area for the "
    "single-area deep-dive.":
        "Elija una Zona, Distrito o Área arriba — escriba en cualquier casilla "
        "para buscar. Se desglosa la selección más específica: elija una zona "
        "para la vista de zona, agregue un distrito para profundizar en él, o "
        "agregue un área para el análisis detallado de esa área.",
    "Companionship": "Compañerismo",
    "Companionship info not found in MISSION_ORG.":
        "No se encontró información del compañerismo en MISSION_ORG.",
    "MISSION_ORG lists no active areas for {scope}.":
        "MISSION_ORG no lista áreas activas para {scope}.",
    "No data yet for {scope}. Submit the nightly form or run a data refresh.":
        "Aún no hay datos para {scope}. Envíe el formulario nocturno o actualice "
        "los datos.",

    # ── Notes ────────────────────────────────────────────────────────────────
    "Notes": "Notas",
    "Show resolved notes": "Mostrar notas resueltas",
    "No notes for this area.": "No hay notas para esta área.",
    "Add Note": "Agregar Nota",
    "Note *": "Nota *",
    "Enter note content...": "Escriba el contenido de la nota...",
    "Tags (comma-separated)": "Etiquetas (separadas por comas)",
    "training, concern": "capacitación, preocupación",
    "Set a follow-up date": "Establecer una fecha de seguimiento",
    "Follow-up Date": "Fecha de Seguimiento",
    "Save Note": "Guardar Nota",
    "Note content is required.": "El contenido de la nota es obligatorio.",
    "Note saved.": "Nota guardada.",

    # ══ Task 10 ═════════════════════════════════════════════════════════════
    # ── Finding Funnel ───────────────────────────────────────────────────────
    "Finding Funnel": "Embudo de Búsqueda",
    "Mission finding & teaching pipeline — auto-synced daily from Tableau":
        "Proceso de búsqueda y enseñanza de la misión — sincronizado a diario desde Tableau",
    "Could not parse Ranking CSV: {err}":
        "No se pudo leer el CSV de Clasificación: {err}",
    "Could not parse Detail CSV: {err}":
        "No se pudo leer el CSV de Detalle: {err}",
    "No finding data yet. It syncs automatically each morning, or upload a "
    "Tableau export in **Manual upload** below.":
        "Aún no hay datos de búsqueda. Se sincronizan automáticamente cada mañana, "
        "o cargue una exportación de Tableau en **Carga manual** más abajo.",
    "Auto-synced · {source} · {at}":
        "Sincronizado automáticamente · {source} · {at}",
    "Uploaded by {by} · {at}": "Cargado por {by} · {at}",
    "Date range": "Rango de fechas",
    "Custom": "Personalizado",
    "Last 7 days": "Últimos 7 días",
    "Last 14 days": "Últimos 14 días",
    "Last 30 days": "Últimos 30 días",
    "Start": "Inicio",
    "End": "Fin",
    "No findings in the selected date range — widen the range to see data.":
        "No hay hallazgos en el rango de fechas seleccionado — amplíe el rango para ver datos.",
    "Finding Pipeline": "Proceso de Búsqueda",
    "Found": "Encontradas",
    "Contact Attempted": "Intento de Contacto",
    "Successfully Contacted": "Contactadas con Éxito",
    "Being Taught": "Recibiendo Lecciones",
    "Attended Church": "Asistió a la Iglesia",
    "Baptism Date Set": "Fecha de Bautismo Fijada",
    "Each stage = people found in range who reached that milestone "
    "(from Tableau finding-event dates).":
        "Cada etapa = personas encontradas en el rango que alcanzaron ese hito "
        "(según las fechas de los eventos de búsqueda de Tableau).",
    "Detail records needed to build the pipeline funnel.":
        "Se requieren registros de detalle para construir el embudo del proceso.",
    "Finding Mix": "Composición de Hallazgos",
    "No detail records to break down.":
        "No hay registros de detalle para desglosar.",
    "Contact Performance": "Desempeño de Contacto",
    "Top Finding Sources": "Principales Fuentes de Hallazgo",
    "Findings by Zone": "Hallazgos por Zona",
    "Findings per Day": "Hallazgos por Día",
    "Detailed Data": "Datos Detallados",
    "Area Rankings (per-area table)":
        "Clasificación de Áreas (tabla por área)",
    "No finding records in the selected range to rank.":
        "No hay registros de búsqueda en el rango seleccionado para clasificar.",
    "{n} areas with activity · sorted by people found "
    "· reflects the selected date range":
        "{n} áreas con actividad · ordenadas por personas encontradas "
        "· refleja el rango de fechas seleccionado",
    "Download Rankings CSV": "Descargar CSV de Clasificación",
    "Finding Records — {n} people": "Registros de Búsqueda — {n} personas",
    "No detail export loaded.": "No se ha cargado ninguna exportación de detalle.",
    "Category": "Categoría",
    "Source": "Fuente",
    "{shown} of {total} records": "{shown} de {total} registros",
    "Showing first 250 — download for the full set.":
        "Mostrando los primeros 250 — descargue el conjunto completo.",
    "Download Records CSV": "Descargar CSV de Registros",
    "Raw Tableau export (all columns)":
        "Exportación de Tableau sin procesar (todas las columnas)",
    "**Ranking — raw**": "**Clasificación — sin procesar**",
    "**Detail — raw**": "**Detalle — sin procesar**",
    "Showing first 200 of {n} rows — download above for all.":
        "Mostrando las primeras 200 de {n} filas — descargue arriba para verlas todas.",
    "Finding Summary PDF": "PDF de Resumen de Búsqueda",
    "Upload the Finding Summary PDF in Manual upload below to view it here.":
        "Cargue el PDF de Resumen de Búsqueda en Carga manual más abajo para verlo aquí.",
    "Download Summary PDF": "Descargar PDF de Resumen",
    "Manual upload / re-sync (optional)":
        "Carga manual / re-sincronización (opcional)",
    "Tableau exports sync automatically every morning. Upload here only "
    "to override with a fresh export.":
        "Las exportaciones de Tableau se sincronizan automáticamente cada mañana. "
        "Cargue aquí solo para reemplazarlas con una exportación nueva.",
    "Detail CSV": "CSV de Detalle",
    "Ranking CSV": "CSV de Clasificación",
    "Summary PDF": "PDF de Resumen",

    # ── Notes page ───────────────────────────────────────────────────────────
    "Filter Notes": "Filtrar Notas",
    "Show Resolved Notes": "Mostrar Notas Resueltas",
    "New Note": "Nota Nueva",
    "Notes List": "Lista de Notas",
    "Search notes": "Buscar notas",
    "Search content…": "Buscar contenido…",
    "Tag": "Etiqueta",
    "No notes match the current filters.":
        "Ninguna nota coincide con los filtros actuales.",
    "No notes yet. Create your first note above.":
        "Aún no hay notas. Cree su primera nota arriba.",
    "Note content cannot be empty.":
        "El contenido de la nota no puede estar vacío.",
    "Zone (optional)": "Zona (opcional)",
    "District (optional)": "Distrito (opcional)",
    "Area (optional)": "Área (opcional)",
    "Set follow-up date": "Establecer fecha de seguimiento",
    "training, concern, zone-x": "capacitación, preocupación, zona-x",
    "Resolve": "Resolver",
    "Re-open": "Reabrir",
    "Resolved": "Resuelta",
    "Edit": "Editar",
    "Delete": "Eliminar",
    "Cancel": "Cancelar",
    "Save Changes": "Guardar Cambios",

    # ── Suggestions ──────────────────────────────────────────────────────────
    "Suggestions": "Sugerencias",
    "Filter": "Filtrar",
    "Search": "Buscar",
    "Search message or name…": "Buscar mensaje o nombre…",
    "Sort": "Ordenar",
    "Newest": "Más recientes",
    "Oldest": "Más antiguas",
    "No suggestions match the current filters.":
        "Ninguna sugerencia coincide con los filtros actuales.",
    # Approval statuses. The Spanish is shown; the English value is what stays
    # in COMPASS_CCSM and what the Apps Script agents read.
    "Pending": "Pendiente",
    "AP Approval": "Aprobación de los AP",
    "Mission President Approval": "Aprobación del Presidente de Misión",
    "MP Approval": "Aprobación del PM",
    "→ MP Approval": "→ Aprobación del PM",
    "Final Approval": "Aprobación Final",
    "Hold": "En Espera",
    "On Hold": "En Espera",
    "Done": "Completada",
    "Rejected": "Rechazada",
    "Reject": "Rechazar",
    "Approved by an AP — send to the Mission President's queue":
        "Aprobada por un AP — enviar a la fila del Presidente de Misión",
    "Move to the Mission President's queue":
        "Mover a la fila del Presidente de Misión",
    "Mission President's final approval — emails ccsm.pmg.compass@gmail.com":
        "Aprobación final del Presidente de Misión — envía correo a ccsm.pmg.compass@gmail.com",
    "Mark as implemented/deployed — emails ccsm.pmg.compass@gmail.com":
        "Marcar como implementada/desplegada — envía correo a ccsm.pmg.compass@gmail.com",
    "Park as a future idea": "Guardar como idea futura",
    "Add a note before Accept/Reject…":
        "Agregue una nota antes de Aceptar/Rechazar…",
    "Reviewer note (optional)": "Nota del revisor (opcional)",

    # ── Action Center ────────────────────────────────────────────────────────
    "Action Center": "Centro de Acción",
    "Everything that needs mission leadership's attention":
        "Todo lo que requiere la atención del liderazgo de la misión",
    "This page is available to mission leadership only.":
        "Esta página está disponible solo para el liderazgo de la misión.",
    "Needs Your Action": "Requiere Su Acción",
    "Nothing needs your action right now.":
        "Nada requiere su acción en este momento.",
    "Review in Suggestions": "Revisar en Sugerencias",
    "Review in Notes": "Revisar en Notas",
    "Review missionary suggestions": "Revisar las sugerencias de los misioneros",
    "Open Maintenance page": "Abrir la página de Mantenimiento",
    "Maintenance": "Mantenimiento",
    "No maintenance issues detected.":
        "No se detectaron problemas de mantenimiento.",
    "Task": "Tarea",
    "Add Task": "Agregar Tarea",
    "Add a Task": "Agregar una Tarea",
    "All open tasks": "Todas las tareas abiertas",
    "No open tasks.": "No hay tareas abiertas.",
    "Task name cannot be empty.":
        "El nombre de la tarea no puede estar vacío.",
    "What needs to happen?": "¿Qué se necesita hacer?",
    "Assign to": "Asignar a",
    "Hand something to another leader — it'll show in their Action Center.":
        "Entregue algo a otro líder — aparecerá en su Centro de Acción.",
    "No other leadership accounts found in MISSION_ORG.":
        "No se encontraron otras cuentas de liderazgo en MISSION_ORG.",
    "Due date": "Fecha límite",
    "Set a due date": "Establecer una fecha límite",
    "Notes (optional)": "Notas (opcional)",
    "Visible to (comma-separated emails, leave blank for everyone)":
        "Visible para (correos separados por comas, deje en blanco para todos)",
    "elder.smith@example.com, sister.jones@example.com":
        "elder.smith@example.com, sister.jones@example.com",

    # ══ Task 11 ═════════════════════════════════════════════════════════════
    # ── Chrome ───────────────────────────────────────────────────────────────
    "Language / Idioma": "Idioma / Language",
    "Sign Out": "Cerrar sesión",
    "Find by missionary": "Buscar por misionero",
    "Clear Zone/District/Area/missionary and show the mission-wide view":
        "Limpiar Zona/Distrito/Área/misionero y mostrar la vista de toda la misión",

    # ── Scores page ──────────────────────────────────────────────────────────
    "Scores": "Puntajes",
    "Area Scores": "Puntajes por Área",
    "Mission Score": "Puntaje de la Misión",
    "Mission Scores": "Puntajes de la Misión",
    "Score Summary": "Resumen de Puntajes",
    "Score Tier Key": "Leyenda de Niveles de Puntaje",
    "Effectiveness Score by Area": "Puntaje de Efectividad por Área",
    "Daily Activity": "Actividad Diaria",
    "Analyze": "Analizar",
    "Raw Data": "Datos sin Procesar",
    "Raw Daily Records": "Registros Diarios sin Procesar",
    "Time Range": "Rango de Tiempo",
    "Days displayed": "Días mostrados",
    "How many days of nightly-form data to show on this page.":
        "Cuántos días de datos del formulario nocturno mostrar en esta página.",
    "Metric": "Métrica",
    "Activity by Category": "Actividad por Categoría",
    "By-area totals": "Totales por área",
    "No data for the selected filters.":
        "No hay datos para los filtros seleccionados.",
    "No data for this category.": "No hay datos para esta categoría.",
    "No daily activity data yet. Re-run the data refresh to populate this page.":
        "Aún no hay datos de actividad diaria. Vuelva a ejecutar la actualización "
        "de datos para llenar esta página.",
    "No scores have been computed yet. Scores are calculated automatically each "
    "Sunday at 11 PM Mountain Time. Run computeAllAreaScores() in Apps Script to "
    "compute scores immediately.":
        "Aún no se han calculado puntajes. Los puntajes se calculan automáticamente "
        "cada domingo a las 11 PM (hora de la montaña). Ejecute computeAllAreaScores() "
        "en Apps Script para calcularlos de inmediato.",
    "Scores are automatically recomputed each Sunday at 11 PM Mountain Time by "
    "the AgentScores Apps Script engine. To trigger an immediate recalculation, "
    "open the Google Apps Script editor for COMPASS_CCSM and run "
    "computeAllAreaScores().":
        "Los puntajes se recalculan automáticamente cada domingo a las 11 PM (hora "
        "de la montaña) mediante el motor AgentScores de Apps Script. Para forzar un "
        "recálculo inmediato, abra el editor de Google Apps Script de COMPASS_CCSM y "
        "ejecute computeAllAreaScores().",

    # ── Metric tabs and summaries ────────────────────────────────────────────
    "Lessons": "Lecciones",
    "Finding": "Búsqueda",
    "Contacts": "Contactos",
    "LSI & Attempts": "LSI e Intentos",
    "Effort": "Esfuerzo",
    "Lessons Summary": "Resumen de Lecciones",
    "Finding Summary": "Resumen de Búsqueda",
    "Contacts Summary": "Resumen de Contactos",
    "Effort Reporting": "Reporte de Esfuerzo",
    "Effort tracking coming soon.": "El seguimiento de esfuerzo estará disponible pronto.",
    "No Effort data available for this area in the selected Time Range.":
        "No hay datos de Esfuerzo para esta área en el Rango de Tiempo seleccionado.",
    "NM Lessons": "Lecciones NM",
    "NM Attempted": "NM Intentados",
    "NM Contacted": "NM Contactados",
    "NM Contacted — by area": "NM Contactados — por área",
    "New People Found": "Nuevas Personas Encontradas",
    "New People Found — by area": "Nuevas Personas Encontradas — por área",
    "LSI Given": "LSI Impartidas",
    "LSI Given & Follow-Ups": "LSI Impartidas y Seguimientos",
    "LSI Given — by area": "LSI Impartidas — por área",
    "Attempts by Type": "Intentos por Tipo",

    # ── Weight editor ────────────────────────────────────────────────────────
    "Edit Score Weights": "Editar los Pesos del Puntaje",
    "Save Config": "Guardar Configuración",
    "Apply weights to": "Aplicar pesos a",
    "Whole Mission (all areas)": "Toda la Misión (todas las áreas)",
    "Choose 'Whole Mission' to set one baseline for every area, or pick a single "
    "area to override it. Area-specific weights win over the mission baseline.":
        "Elija 'Toda la Misión' para fijar una base única para cada área, o elija un "
        "área para reemplazarla. Los pesos por área tienen prioridad sobre la base "
        "de la misión.",
    "Editing the **mission-wide baseline**. These weights apply to every area "
    "unless that area has its own override.":
        "Está editando la **base de toda la misión**. Estos pesos se aplican a cada "
        "área, salvo que esa área tenga su propia configuración.",
    "**How the Effectiveness score is built.** Each area's Effectiveness score "
    "is a blend of three components — **Effort**, **Skill**, and **Key "
    "Indicators (KI)**. Set how much each component counts in *Component Mix* "
    "below, then fine-tune every individual metric (lessons, contacts, "
    "referrals, door attempts, weekly KIs, etc.) inside each component tab.":
        "**Cómo se construye el puntaje de Efectividad.** El puntaje de Efectividad "
        "de cada área combina tres componentes — **Esfuerzo**, **Habilidad** e "
        "**Indicadores Clave (IC)**. Defina cuánto cuenta cada componente en "
        "*Composición de Componentes* más abajo, y luego ajuste cada métrica "
        "individual (lecciones, contactos, referencias, intentos de puerta, IC "
        "semanales, etc.) dentro de la pestaña de cada componente.",
    "##### Component Mix": "##### Composición de Componentes",
    "##### Metric Weights": "##### Pesos de las Métricas",
    "How much each component counts toward Effectiveness. Must sum to 1.0 "
    "(e.g. Effort 0.30 + Skill 0.30 + KI 0.40).":
        "Cuánto aporta cada componente a la Efectividad. Debe sumar 1.0 "
        "(por ejemplo, Esfuerzo 0.30 + Habilidad 0.30 + IC 0.40).",
    "Effort Weight": "Peso del Esfuerzo",
    "Skill Weight": "Peso de la Habilidad",
    "KI Weight": "Peso de los IC",
    "Effort Metrics": "Métricas de Esfuerzo",
    "Skill Metrics": "Métricas de Habilidad",
    "Key Indicator Metrics": "Métricas de Indicadores Clave",
    "Every metric from the nightly and weekly forms, with the weight it carries. "
    "Each box label shows the recommended baseline (rec). A weight of 0 means the "
    "metric doesn't count. The engine normalises by component total, so relative "
    "proportions are what matter.":
        "Cada métrica de los formularios nocturno y semanal, con el peso que tiene. "
        "La etiqueta de cada casilla muestra la base recomendada (rec). Un peso de 0 "
        "significa que la métrica no cuenta. El motor normaliza según el total del "
        "componente, así que lo que importa son las proporciones relativas.",
    "Legacy / unused — the Effort score is now computed from the mission "
    "president's fixed weekly expectations per area type, not these per-metric "
    "weights. Kept for reference only.":
        "Obsoleto / sin uso — el puntaje de Esfuerzo ahora se calcula a partir de las "
        "expectativas semanales fijas del presidente de misión por tipo de área, no de "
        "estos pesos por métrica. Se mantiene solo como referencia.",
    "Nightly-form quality signals — how effectively the area is working. "
    "Metrics left at 0 don't count toward Skill.":
        "Señales de calidad del formulario nocturno — con cuánta eficacia trabaja el "
        "área. Las métricas dejadas en 0 no cuentan para la Habilidad.",
    "Weekly-form Key Indicators — Pew, Date, Gate, Renew, RC.":
        "Indicadores Clave del formulario semanal — Pew, Date, Gate, Renew, RC.",
    "Effort uses its own tiers — meeting the mission president's weekly "
    "expectations exactly scores 75, so its bar is green above 75, yellow 50–75, "
    "red below 50 (Skill/KI/Effectiveness keep 70/50).":
        "El Esfuerzo usa sus propios niveles — cumplir exactamente las expectativas "
        "semanales del presidente de misión da 75, así que su barra es verde sobre 75, "
        "amarilla entre 50 y 75, y roja bajo 50 (Habilidad/IC/Efectividad mantienen "
        "70/50).",

    # ── Analyze tab ──────────────────────────────────────────────────────────
    "Trend Projection": "Proyección de Tendencia",
    "Metric to project": "Métrica a proyectar",
    "Pick any nightly-form or weekly-form metric to see its projection.":
        "Elija cualquier métrica del formulario nocturno o semanal para ver su proyección.",
    "Mission-wide totals from completed weeks (current in-progress week "
    "excluded), with next week projected by linear regression and an 80% "
    "confidence range.":
        "Totales de toda la misión de las semanas completadas (se excluye la semana en "
        "curso), con la próxima semana proyectada por regresión lineal y un rango de "
        "confianza del 80%.",
    "High confidence — the trend is statistically significant.":
        "Confianza alta — la tendencia es estadísticamente significativa.",
    "Low confidence — the recent weeks aren't a statistically significant trend. "
    "Treat this as a rough estimate, not a forecast.":
        "Confianza baja — las semanas recientes no constituyen una tendencia "
        "estadísticamente significativa. Tómelo como una estimación aproximada, no "
        "como un pronóstico.",
    "No history available yet for this metric.":
        "Aún no hay historial disponible para esta métrica.",
    "Anomaly Threshold (%)": "Umbral de Anomalía (%)",
    "Flag areas where this week's value is below this % of their 4-week average.":
        "Marcar las áreas cuyo valor de esta semana esté bajo este % de su promedio "
        "de 4 semanas.",

    # A markdown horizontal rule, not prose - mapped to itself so the coverage
    # gate stays strict without pretending a divider was translated.
    "---": "---",
}
