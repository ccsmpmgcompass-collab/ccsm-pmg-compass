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

    # ══ Task 12 + leftovers ═════════════════════════════════════════════════
    # ── Auth (app/auth/auth.py) ──────────────────────────────────────────────
    # These are what a locked-out user sees. They cannot reach the language
    # switch to fix it, so leaving them English would strand a Spanish speaker.
    "Access denied. You must be signed in with an approved Google account. "
    "Contact the mission office if you need access.":
        "Acceso denegado. Debe iniciar sesión con una cuenta de Google aprobada. "
        "Comuníquese con la oficina de la misión si necesita acceso.",
    "Access denied. Your account is not approved for PMG Compass. "
    "Contact the mission office to request access.":
        "Acceso denegado. Su cuenta no está aprobada para PMG Compass. "
        "Comuníquese con la oficina de la misión para solicitar acceso.",
    "Could not verify your identity. Please sign out and sign back in.":
        "No se pudo verificar su identidad. Cierre sesión y vuelva a iniciarla.",
    "Your session has expired. Please sign in again.":
        "Su sesión ha expirado. Por favor inicie sesión nuevamente.",

    # ── Breakdowns engine ────────────────────────────────────────────────────
    "Period": "Período",
    "X-Axis": "Eje X",
    "Reset Graph ↻": "Restablecer Gráfico ↻",
    "No area data for the trend chart.":
        "No hay datos de área para el gráfico de tendencia.",
    "No daily-log metrics available for this group yet.":
        "Aún no hay métricas del registro diario para este grupo.",
    "No weekly reporting weeks are due yet.":
        "Aún no vence ninguna semana de reporte semanal.",
    "At Sacrament is a weekly headcount, not unique people — someone who "
    "attends several Sundays in this period is added again each week, so it "
    "can run higher than Taught (which counts each person once).":
        "En Sacramental es un conteo semanal de asistentes, no de personas únicas — "
        "alguien que asiste varios domingos en este período se cuenta de nuevo cada "
        "semana, así que puede superar a Enseñadas (que cuenta cada persona una vez).",

    # ── Goals page ───────────────────────────────────────────────────────────
    "Goals": "Metas",
    "Save Goals": "Guardar Metas",
    "Monthly Goals": "Metas Mensuales",
    "Save Monthly Goals": "Guardar Metas Mensuales",
    "Save Mission Goals": "Guardar Metas de la Misión",
    "Set Mission Goals — This Month": "Fijar las Metas de la Misión — Este Mes",
    "Mission Goals vs Actuals — This Month":
        "Metas de la Misión vs Reales — Este Mes",
    "Goals vs Actuals by Area — Latest Week":
        "Metas vs Reales por Área — Última Semana",
    "Goal from GOALS_CONFIG tab. Actual from the most recent week in WEEKLY_KI. "
    "Color: green ≥ 100%  amber ≥ 75%  red < 75%.":
        "La meta proviene de la pestaña GOALS_CONFIG. El valor real proviene de la "
        "semana más reciente en WEEKLY_KI. Color: verde ≥ 100%  ámbar ≥ 75%  rojo < 75%.",
    "Area Goal Customization": "Personalización de Metas por Área",
    "Area Expectation Settings": "Configuración de Expectativas por Área",
    "Area expectations saved.": "Expectativas de área guardadas.",
    "Save Area Expectations": "Guardar Expectativas de Área",
    "Add Area Override": "Agregar Excepción de Área",
    "Reset to Mission Defaults": "Restablecer a los Valores de la Misión",
    "Select Area": "Seleccionar Área",
    "Specific area": "Área específica",
    "Pick an area…": "Elija un área…",
    "Pick an area first.": "Primero elija un área.",
    "Pick a cadence first.": "Primero elija una frecuencia.",
    "Pick an indicator first.": "Primero elija un indicador.",
    "Or find by missionary name": "O busque por nombre de misionero",
    "Filter by Zone": "Filtrar por Zona",
    "Indicator": "Indicador",
    "Cadence": "Frecuencia",
    "weekly": "semanal",
    "monthly": "mensual",
    "SELECT CADENCE": "ELIJA LA FRECUENCIA",
    "SELECT INDICATOR": "ELIJA EL INDICADOR",
    "Target": "Meta",
    "Add Category": "Agregar Categoría",
    "Add another indicator to this category:":
        "Agregar otro indicador a esta categoría:",
    "Add": "Agregar",
    "Remove": "Quitar",
    "Save": "Guardar",
    "Save All Recommended": "Guardar Todo lo Recomendado",
    "FILL ALL RECOMMENDED": "LLENAR TODO LO RECOMENDADO",
    "RECOMMEND ALL AREA GOALS": "RECOMENDAR TODAS LAS METAS DE ÁREA",
    "Recommended Goal Nudge": "Ajuste de la Meta Recomendada",
    "Metric to preview": "Métrica a previsualizar",
    "Other Metrics": "Otras Métricas",
    "Nightly Form Goals (weekly totals)":
        "Metas del Formulario Nocturno (totales semanales)",
    "Yes, reset": "Sí, restablecer",
    "✏️": "✏️",
    "➕ Add a custom expectation category":
        "➕ Agregar una categoría de expectativa personalizada",
    "No active area names found.": "No se encontraron nombres de áreas activas.",
    "No active areas found. Check the MISSION_ORG tab.":
        "No se encontraron áreas activas. Revise la pestaña MISSION_ORG.",
    "No area goal data matches the current filter.":
        "Ningún dato de metas de área coincide con el filtro actual.",
    "No custom goals saved for this area yet — enter values and save.":
        "Aún no hay metas personalizadas guardadas para esta área — ingrese valores y guarde.",
    "No custom goals to reset for this area.":
        "No hay metas personalizadas que restablecer para esta área.",
    "No goals or actuals data available yet.":
        "Aún no hay datos de metas ni de valores reales.",
    "No completed weeks for this metric yet.":
        "Aún no hay semanas completadas para esta métrica.",
    "No weekly history for this metric yet.":
        "Aún no hay historial semanal para esta métrica.",
    "Compute the recommended weekly and monthly goals for every active area, "
    "preview them, then save all at once.":
        "Calcule las metas semanales y mensuales recomendadas para cada área activa, "
        "revíselas, y luego guárdelas todas a la vez.",
    "Nothing here saves itself — edits below (including added or removed "
    "indicators and categories) only take effect everywhere once you press "
    "**Save Area Expectations**.":
        "Nada aquí se guarda solo — los cambios de abajo (incluidos los indicadores y "
        "categorías agregados o eliminados) solo surten efecto en todas partes cuando "
        "presione **Guardar Expectativas de Área**.",
    "Every Recommended (REC) badge on Area Goals and Mission Goals recommends "
    "that area's (or the whole mission's) own average performance, stretched up "
    "by this percentage. 0% = the plain average itself; 10% = a light stretch "
    "(the original behavior); 100% = double the average. Example: an area "
    "averaging 10/week shows REC 11 at 10%, REC 15 at 50%, and REC 20 at 100%. "
    "Applies mission-wide, everywhere a REC badge appears.":
        "Cada distintivo Recomendado (REC) en Metas de Área y Metas de la Misión "
        "recomienda el propio promedio de desempeño de esa área (o de toda la misión), "
        "aumentado por este porcentaje. 0% = el promedio tal cual; 10% = un aumento leve "
        "(el comportamiento original); 100% = el doble del promedio. Ejemplo: un área con "
        "un promedio de 10 por semana muestra REC 11 al 10%, REC 15 al 50% y REC 20 al "
        "100%. Se aplica en toda la misión, dondequiera que aparezca un distintivo REC.",
    "Set a weekly goal for every nightly and weekly form metric for this area. "
    "Saved goals appear on the Breakdowns page's area view and roll up into "
    "zone-level goals on its zone view. Gate, Date, New, Pew, Renew, and Mate "
    "additionally get a MONTHLY goal further down, stored separately.":
        "Fije una meta semanal para cada métrica de los formularios nocturno y semanal "
        "de esta área. Las metas guardadas aparecen en la vista de área de la página "
        "Desgloses y se suman en metas por zona en su vista de zona. Gate, Date, New, "
        "Pew, Renew y Mate además reciben una meta MENSUAL más abajo, guardada aparte.",
    "Weekly and monthly expectations by area category — the single source of "
    "truth for the Goals pages' \"/N\" fractions (including Monthly Goals' Gate "
    "and Mission Goals' totals), the Breakdowns trend chart's expectation lines "
    "(any indicator with an expectation gets a line when that metric is selected "
    "there), and the Scores page's Effort score. Save, and every page reflects "
    "it immediately. A category is matched off each area's MISSION_ORG "
    "Language_Type or area name — Haitian, Creole and French are also matched by "
    "area name even with a blank/English Language_Type — and a category named "
    "exactly after one area overrides everything else for just that area.":
        "Expectativas semanales y mensuales por categoría de área — la única fuente de "
        "verdad para las fracciones \"/N\" de las páginas de Metas (incluidos Gate en "
        "Metas Mensuales y los totales de Metas de la Misión), las líneas de expectativa "
        "del gráfico de tendencia de Desgloses (cualquier indicador con expectativa "
        "recibe una línea cuando esa métrica se selecciona ahí), y el puntaje de Esfuerzo "
        "de la página Puntajes. Guarde, y cada página lo reflejará de inmediato. La "
        "categoría se determina según el Language_Type de MISSION_ORG de cada área o el "
        "nombre del área — haitiano, creole y francés también se detectan por el nombre "
        "del área aunque el Language_Type esté vacío o en inglés — y una categoría "
        "nombrada exactamente como un área prevalece sobre todo lo demás solo para esa área.",
    "Custom category — matched by substring against an area's Language_Type or "
    "its own name.":
        "Categoría personalizada — se detecta por coincidencia parcial con el "
        "Language_Type de un área o con su propio nombre.",
    "Type a language (e.g. \"Japanese\") or any keyword (e.g. \"BYU\") — it "
    "matches every area whose Language_Type OR area name contains it, so \"BYU\" "
    "catches BYU East and BYU North whatever their languages. Add its indicators "
    "in its own section above once the category exists.":
        "Escriba un idioma (por ejemplo \"japonés\") o cualquier palabra clave (por "
        "ejemplo \"BYU\") — coincide con toda área cuyo Language_Type O nombre lo "
        "contenga, así que \"BYU\" abarca BYU East y BYU North sin importar sus idiomas. "
        "Agregue sus indicadores en su propia sección más arriba una vez creada la categoría.",
    "Enter a language or keyword first.": "Primero ingrese un idioma o palabra clave.",
    "— or override ONE specific area: pick it here and it gets its own section "
    "above, pre-filled with what it currently resolves to. Its numbers then beat "
    "its language category everywhere (fractions, Breakdowns lines, Effort score).":
        "— o defina una excepción para UNA área específica: elíjala aquí y recibirá su "
        "propia sección arriba, precargada con lo que actualmente le corresponde. Sus "
        "números entonces prevalecen sobre su categoría de idioma en todas partes "
        "(fracciones, líneas de Desgloses, puntaje de Esfuerzo).",
    "Only the Mission President or Assistants can change these.":
        "Solo el Presidente de Misión o los Asistentes pueden cambiar esto.",

    # ── Maintenance: status and snapshot ─────────────────────────────────────
    "Data Snapshot": "Instantánea de Datos",
    "Data Freshness": "Actualidad de los Datos",
    "Compliance Today": "Cumplimiento de Hoy",
    "Areas Submitted Today": "Áreas que Enviaron Hoy",
    "Submitted This Week": "Enviado Esta Semana",
    "All-Time Compliance": "Cumplimiento Histórico",
    "Number of areas that submitted their nightly report today.":
        "Cantidad de áreas que enviaron su reporte nocturno hoy.",
    "Percentage of active areas that submitted today.":
        "Porcentaje de áreas activas que enviaron hoy.",
    "Total area-day submissions received so far this week (Mon–Sun).":
        "Total de envíos por área y día recibidos hasta ahora esta semana (lun–dom).",
    "Submissions received vs expected across all areas.":
        "Envíos recibidos frente a los esperados en todas las áreas.",
    "How recently each pipeline stage wrote data. Stale rows here mean an agent "
    "or ingestion run didn't fire — check the agent runs below, then the Apps "
    "Script triggers.":
        "Hace cuánto escribió datos cada etapa del proceso. Las filas desactualizadas "
        "aquí significan que un agente o una carga de datos no se ejecutó — revise las "
        "ejecuciones de agentes más abajo, y luego los activadores de Apps Script.",
    "No metadata available yet — Agent5A may not have run today.":
        "Aún no hay metadatos disponibles — es posible que Agent5A no se haya ejecutado hoy.",

    # ── Maintenance: agents and runbook ──────────────────────────────────────
    "Agent Runs": "Ejecuciones de Agentes",
    "Weekly To-Do": "Tareas Semanales",
    "Raw log — last 50 runs": "Registro sin procesar — últimas 50 ejecuciones",
    "No failed agent runs in the last 14 days.":
        "No hubo ejecuciones de agentes fallidas en los últimos 14 días.",
    "Every Apps Script agent appends a row to AGENT_RUN_LOG when it runs. An "
    "agent missing from the last-run table, or a red status, means its trigger "
    "didn't fire or the run errored.":
        "Cada agente de Apps Script agrega una fila a AGENT_RUN_LOG cuando se ejecuta. "
        "Un agente ausente de la tabla de últimas ejecuciones, o un estado en rojo, "
        "significa que su activador no se disparó o que la ejecución falló.",
    "Schedules shown are the intended ones — Apps Script → Triggers (clock icon) "
    "is the live truth.":
        "Los horarios mostrados son los previstos — Apps Script → Activadores (icono de "
        "reloj) es la verdad real.",
    "AGENT_RUN_LOG is empty or unreadable. If agents are running, they log there "
    "on every run — an empty log means the whole chain may be stopped.":
        "AGENT_RUN_LOG está vacío o no se puede leer. Si los agentes se están "
        "ejecutando, registran ahí en cada ejecución — un registro vacío puede "
        "significar que toda la cadena está detenida.",
    "Runbook": "Guía de Operación",
    "If the app is stale, blank, or erroring":
        "Si la aplicación está desactualizada, en blanco o con errores",
    "If agents stopped running or emails stopped sending":
        "Si los agentes dejaron de ejecutarse o los correos dejaron de enviarse",
    "Everything This System Is Connected To":
        "Todo lo que Está Conectado a Este Sistema",
    "If the app is ever wrong or down, COMPASS_CCSM is the source of truth — "
    "everything the mission reports lives there.":
        "Si la aplicación alguna vez se equivoca o deja de funcionar, COMPASS_CCSM es la "
        "fuente de verdad — todo lo que reporta la misión vive ahí.",
    "A required tab going missing usually means someone renamed or deleted it in "
    "COMPASS_CCSM. Restore the exact name — agents and this app look tabs up by "
    "name.":
        "Que falte una pestaña requerida suele significar que alguien la renombró o "
        "eliminó en COMPASS_CCSM. Restaure el nombre exacto — los agentes y esta "
        "aplicación buscan las pestañas por nombre.",

    # ── Maintenance: app controls ────────────────────────────────────────────
    "App Controls": "Controles de la Aplicación",
    "Connection & Configuration": "Conexión y Configuración",
    "Environment": "Entorno",
    "Quick Links": "Enlaces Rápidos",
    "Maintenance section": "Sección de mantenimiento",
    "Section": "Sección",
    "Clear data cache": "Borrar la caché de datos",
    "Data cache cleared — pages will refetch on next load.":
        "Caché de datos borrada — las páginas volverán a consultar en la próxima carga.",
    "Drops all 5-minute cached reads so every page refetches live from "
    "COMPASS_CCSM. Use when the Sheet was just edited and pages still show old "
    "numbers.":
        "Descarta todas las lecturas en caché de 5 minutos para que cada página vuelva a "
        "consultar en vivo desde COMPASS_CCSM. Úselo cuando la hoja acaba de editarse y "
        "las páginas siguen mostrando números antiguos.",
    "Reset Google Sheets connection": "Restablecer la conexión con Google Sheets",
    "Connection reset — it will reconnect on next read.":
        "Conexión restablecida — se reconectará en la próxima lectura.",
    "Rebuilds the gspread client and reopens the spreadsheet, plus clears the "
    "data cache. Use when reads fail with auth/connection errors that a cache "
    "clear doesn't fix.":
        "Reconstruye el cliente gspread y vuelve a abrir la hoja de cálculo, además de "
        "borrar la caché de datos. Úselo cuando las lecturas fallan con errores de "
        "autenticación o conexión que no se corrigen borrando la caché.",
    "These only affect this Streamlit app — never the Sheet, the agents, or any "
    "emails. Safe to use any time.":
        "Esto solo afecta a esta aplicación de Streamlit — nunca a la hoja, a los agentes "
        "ni a los correos. Es seguro usarlo en cualquier momento.",
    "PMG Compass data updates automatically every day at noon from Google "
    "Sheets. No manual refresh is needed.":
        "Los datos de PMG Compass se actualizan automáticamente todos los días al "
        "mediodía desde Google Sheets. No hace falta actualizar manualmente.",
    "Open COMPASS_CCSM ↗": "Abrir COMPASS_CCSM ↗",
    "Nightly form ↗": "Formulario nocturno ↗",
    "Weekly form ↗": "Formulario semanal ↗",

    # ── Maintenance: test mode ───────────────────────────────────────────────
    "Test Mode": "Modo de Prueba",
    "Enable Test Mode": "Activar el Modo de Prueba",
    "Disable Test Mode (Go Live)": "Desactivar el Modo de Prueba (Salir en Vivo)",
    "**TEST MODE is ON.** All agent emails are redirected to the test inbox and "
    "data is written to TEST_* tabs. Missionaries receiving nothing is expected "
    "while this is on.":
        "**EL MODO DE PRUEBA ESTÁ ACTIVO.** Todos los correos de los agentes se redirigen "
        "a la bandeja de prueba y los datos se escriben en las pestañas TEST_*. Que los "
        "misioneros no reciban nada es lo esperado mientras esto esté activo.",
    "**System is LIVE.** Test Mode is off.":
        "**El sistema está EN VIVO.** El Modo de Prueba está desactivado.",
    "I understand missionaries stop receiving real emails while Test Mode is on.":
        "Entiendo que los misioneros dejan de recibir correos reales mientras el Modo de "
        "Prueba esté activo.",
    "Only mission leadership can change test mode.":
        "Solo el liderazgo de la misión puede cambiar el modo de prueba.",

    # ── Maintenance: AGENT_CONFIG ────────────────────────────────────────────
    "Agent Configuration (AGENT_CONFIG)": "Configuración de Agentes (AGENT_CONFIG)",
    "Filter settings": "Filtrar configuraciones",
    "Add setting": "Agregar configuración",
    "➕ Add a new setting": "➕ Agregar una configuración nueva",
    "Key": "Clave",
    "Value": "Valor",
    "New value": "Valor nuevo",
    "Added by": "Agregado por",
    "e.g. ESCALATION_NIGHTLY_HOUR": "por ejemplo, ESCALATION_NIGHTLY_HOUR",
    "Every setting the Apps Script agents read at run time. Edits here take "
    "effect on the next agent run automatically — no Apps Script paste needed. "
    "Secret-looking values are masked; editing one replaces it outright.":
        "Cada configuración que los agentes de Apps Script leen al ejecutarse. Los "
        "cambios aquí surten efecto automáticamente en la próxima ejecución — no hace "
        "falta pegar nada en Apps Script. Los valores que parecen secretos se enmascaran; "
        "editar uno lo reemplaza por completo.",
    "This value is masked — whatever you type replaces it. Leave and Cancel to "
    "keep it.":
        "Este valor está enmascarado — lo que escriba lo reemplazará. Salga y cancele "
        "para conservarlo.",
    "Only useful for a key an agent actually reads — unknown keys are ignored "
    "harmlessly.":
        "Solo es útil para una clave que un agente realmente lea — las claves "
        "desconocidas se ignoran sin causar problemas.",
    "Only mission leadership can edit settings.":
        "Solo el liderazgo de la misión puede editar la configuración.",
    "AGENT_CONFIG is missing or empty.": "AGENT_CONFIG falta o está vacía.",
    "AGENT_CONFIG header row changed — expected Config_Key and Value columns. "
    "Fix the header in the Sheet.":
        "La fila de encabezado de AGENT_CONFIG cambió — se esperaban las columnas "
        "Config_Key y Value. Corrija el encabezado en la hoja.",
    "The failsafe/escalation email times (nightly ~10 AM, weekly ~8:45 PM MT) "
    "are baked into Apps Script triggers today. To control them from here: paste "
    "**docs/EscalationHoursConfig.gs** into the Apps Script editor once and run "
    "its setup — after that, the ESCALATION_NIGHTLY_HOUR / "
    "ESCALATION_WEEKLY_HOUR settings above are what set the send times.":
        "Los horarios de los correos de resguardo/escalamiento (nocturno ~10 AM, semanal "
        "~8:45 PM MT) hoy están fijados en los activadores de Apps Script. Para "
        "controlarlos desde aquí: pegue **docs/EscalationHoursConfig.gs** en el editor de "
        "Apps Script una vez y ejecute su configuración — después de eso, los ajustes "
        "ESCALATION_NIGHTLY_HOUR / ESCALATION_WEEKLY_HOUR de arriba son los que definen "
        "las horas de envío.",

    # ── Maintenance: questions config ────────────────────────────────────────
    "Form Question Configuration (QUESTIONS_CONFIG)":
        "Configuración de Preguntas del Formulario (QUESTIONS_CONFIG)",
    "Form": "Formulario",
    "NIGHTLY": "NOCTURNO",
    "WEEKLY": "SEMANAL",
    "Data type": "Tipo de dato",
    "INTEGER": "ENTERO",
    "TEXT": "TEXTO",
    "DATE": "FECHA",
    "Question": "Pregunta",
    "Add question": "Agregar pregunta",
    "➕ Add a question": "➕ Agregar una pregunta",
    "Save question changes": "Guardar los cambios de las preguntas",
    "Push to Google Forms": "Enviar a Google Forms",
    "Push questions to the Google Forms": "Enviar las preguntas a Google Forms",
    "Syncing both forms — this can take a minute...":
        "Sincronizando ambos formularios — esto puede tardar un minuto...",
    "Question text — exactly as it should appear on the form":
        "Texto de la pregunta — exactamente como debe aparecer en el formulario",
    "Short display name (charts and reports)":
        "Nombre corto para mostrar (gráficos e informes)",
    "Metric key — leave blank to derive from the display name":
        "Clave de la métrica — déjela en blanco para derivarla del nombre para mostrar",
    "e.g. Non-member Lessons": "por ejemplo, Lecciones a no miembros",
    "e.g. NM Lessons": "por ejemplo, Lecciones NM",
    "e.g. contacts_made": "por ejemplo, contacts_made",
    "Question text and a metric key (or display name) are required.":
        "Se requiere el texto de la pregunta y una clave de métrica (o nombre para mostrar).",
    "That exact question is already on this form.":
        "Esa pregunta exacta ya está en este formulario.",
    "QUESTIONS_CONFIG is missing or empty.": "QUESTIONS_CONFIG falta o está vacía.",
    "QUESTIONS_CONFIG has no metrics defined.":
        "QUESTIONS_CONFIG no tiene métricas definidas.",
    "No metrics are configured yet — check QUESTIONS_CONFIG on the Maintenance page.":
        "Aún no hay métricas configuradas — revise QUESTIONS_CONFIG en la página de "
        "Mantenimiento.",
    # Names the source form, so it keeps the mission's own capitalization of it
    # (Formulario Semanal), matching how the nightly/weekly forms are referred
    # to elsewhere in the app.
    "{metric} — Weekly Form": "{metric} — Formulario Semanal",
    "The questions on the nightly and weekly report forms. Active drives what "
    "the agents process and what most pages show. Toggling here (or adding a "
    "question) does **not** touch the Google Forms until you push below — the "
    "push adds active questions to every zone's section and removes inactive "
    "ones.":
        "Las preguntas de los formularios de reporte nocturno y semanal. La casilla "
        "Activa determina lo que procesan los agentes y lo que muestran la mayoría de las "
        "páginas. Cambiarla aquí (o agregar una pregunta) **no** modifica los Google "
        "Forms hasta que envíe los cambios abajo — el envío agrega las preguntas activas "
        "a la sección de cada zona y quita las inactivas.",
    "Adds every Active question to every zone section of its form and deletes "
    "questions that are no longer active. Already-collected responses in the "
    "Sheet are never touched.":
        "Agrega cada pregunta Activa a la sección de cada zona de su formulario y elimina "
        "las preguntas que ya no están activas. Las respuestas ya recopiladas en la hoja "
        "nunca se modifican.",
    "Adds the question to QUESTIONS_CONFIG as Active. It reaches the real Google "
    "Forms when you push below, and the agents start processing it on their next "
    "run. Note: a few hard-coded metric lists (the Breakdowns metric picker) "
    "still need a code change to show a brand-new metric.":
        "Agrega la pregunta a QUESTIONS_CONFIG como Activa. Llega a los Google Forms "
        "reales cuando envía los cambios abajo, y los agentes empiezan a procesarla en su "
        "próxima ejecución. Nota: algunas listas de métricas fijas en el código (el "
        "selector de métricas de Desgloses) todavía requieren un cambio de código para "
        "mostrar una métrica totalmente nueva.",
    "The question-sync web app isn't deployed yet, so pushing from here is "
    "disabled. One-time setup: paste **docs/FormQuestionSyncWebApp.gs** into the "
    "COMPASS_CCSM Apps Script editor, deploy it as a web app, then add "
    "QUESTION_SYNC_WEBAPP_URL and QUESTION_SYNC_WEBAPP_SECRET to this app's "
    "secrets. Until then, form questions have to be edited in the Google Forms "
    "editor by hand.":
        "La aplicación web de sincronización de preguntas aún no está desplegada, así que "
        "el envío desde aquí está deshabilitado. Configuración por única vez: pegue "
        "**docs/FormQuestionSyncWebApp.gs** en el editor de Apps Script de COMPASS_CCSM, "
        "despliéguelo como aplicación web, y luego agregue QUESTION_SYNC_WEBAPP_URL y "
        "QUESTION_SYNC_WEBAPP_SECRET a los secretos de esta aplicación. Hasta entonces, "
        "las preguntas del formulario deben editarse a mano en el editor de Google Forms.",

    # ── Maintenance: knowledge base ──────────────────────────────────────────
    "Add a Question & Answer": "Agregar una Pregunta y Respuesta",
    "Answer": "Respuesta",
    "Keywords": "Palabras clave",
    "Language or keyword": "Idioma o palabra clave",
    "Search the knowledge base": "Buscar en la base de conocimiento",
    "Filter by any word in the question, answer, or keywords":
        "Filtrar por cualquier palabra de la pregunta, la respuesta o las palabras clave",
    "What the missionary asked — or is likely to ask":
        "Lo que preguntó el misionero — o lo que probablemente pregunte",
    "The answer AgentQA should send back":
        "La respuesta que AgentQA debe enviar",
    "comma-separated — leave blank to auto-generate from the Q&A":
        "separadas por comas — deje en blanco para generarlas automáticamente a partir de "
        "la pregunta y la respuesta",
    "e.g. EMAIL, TEST, FORM": "por ejemplo, EMAIL, TEST, FORM",
    "Both the question and the answer are required.":
        "Se requieren tanto la pregunta como la respuesta.",
    "Only mission leadership can add knowledge-base entries.":
        "Solo el liderazgo de la misión puede agregar entradas a la base de conocimiento.",
    "AgentQA auto-answers missionary questions from the Questions & Suggestions "
    "form using the KNOWLEDGE_BASE tab — every entry added here makes the next "
    "question more likely to be answered without a human. New entries take the "
    "next sequential ID and are live for the very next question; no code change "
    "needed.":
        "AgentQA responde automáticamente las preguntas de los misioneros del formulario "
        "de Preguntas y Sugerencias usando la pestaña KNOWLEDGE_BASE — cada entrada "
        "agregada aquí hace más probable que la próxima pregunta se responda sin "
        "intervención humana. Las entradas nuevas toman el siguiente ID secuencial y "
        "quedan activas para la siguiente pregunta; no se requiere cambio de código.",
    "KNOWLEDGE_BASE tab is missing — run setupKnowledgeBase() once from the Apps "
    "Script editor (AgentQA.gs) to create and seed it.":
        "Falta la pestaña KNOWLEDGE_BASE — ejecute setupKnowledgeBase() una vez desde el "
        "editor de Apps Script (AgentQA.gs) para crearla y poblarla.",
    "Areas Involved": "Áreas Involucradas",

    # The architecture overview block on the Maintenance page.
    "- **COMPASS_CCSM (Google Sheet)** — the only data store. Every tab the "
    "agents and this app read or write lives there (link above).\n"
    "- **Google Forms** — the nightly + weekly report forms (links above) write "
    "into NIGHTLY_FORM_RAW / WEEKLY_FORM_RAW; the Questions & Suggestions form "
    "feeds AgentQA.\n"
    "- **Apps Script agents** — live *inside* COMPASS_CCSM (Extensions → Apps "
    "Script). The table below lists them; `docs/` in the git repo holds "
    "reference copies, but **only code pasted into the online editor actually "
    "runs**.\n"
    "- **This app (Streamlit Cloud)** — auto-deploys the `main` branch. Reads "
    "COMPASS_CCSM via the service account; writes Notes, Score Config, and the "
    "tabs this page edits.\n"
    "- **GitHub Actions** — cloud buttons in this app dispatch "
    "`transfer-roster-pull.yml` (portal roster → TRANSFER_IMPORT), "
    "`referral-scraper.yml` (referrals → REFERRAL_DATA), and "
    "`tableau-reports.yml` (quarterly Tableau exports).\n"
    "- **Gemini API** — the Home-page chatbot, AgentQA's auto-answers, and "
    "Agent1C's leadership narratives.":
        "- **COMPASS_CCSM (Google Sheet)** — el único almacén de datos. Cada pestaña que "
        "los agentes y esta aplicación leen o escriben vive ahí (enlace arriba).\n"
        "- **Google Forms** — los formularios de reporte nocturno y semanal (enlaces "
        "arriba) escriben en NIGHTLY_FORM_RAW / WEEKLY_FORM_RAW; el formulario de "
        "Preguntas y Sugerencias alimenta a AgentQA.\n"
        "- **Agentes de Apps Script** — viven *dentro* de COMPASS_CCSM (Extensiones → "
        "Apps Script). La tabla de abajo los lista; `docs/` en el repositorio git "
        "contiene copias de referencia, pero **solo el código pegado en el editor en "
        "línea se ejecuta realmente**.\n"
        "- **Esta aplicación (Streamlit Cloud)** — se despliega automáticamente desde la "
        "rama `main`. Lee COMPASS_CCSM mediante la cuenta de servicio; escribe Notas, la "
        "Configuración de Puntajes y las pestañas que edita esta página.\n"
        "- **GitHub Actions** — los botones en la nube de esta aplicación disparan "
        "`transfer-roster-pull.yml` (lista del portal → TRANSFER_IMPORT), "
        "`referral-scraper.yml` (referencias → REFERRAL_DATA) y `tableau-reports.yml` "
        "(exportaciones trimestrales de Tableau).\n"
        "- **API de Gemini** — el chatbot de la página de Inicio, las respuestas "
        "automáticas de AgentQA y las narrativas de liderazgo de Agent1C.",

    "1. **Clear data cache** (button above). Fixes 90% of \"the Sheet says X but "
    "the app says Y\" — reads are cached for 5 minutes.\n"
    "2. **Reset the Sheets connection** if reads are failing outright.\n"
    "3. **Reboot the app**: Streamlit Cloud → the app's ⋮ menu → Reboot. Also "
    "forces the latest commit from `main` to deploy.\n"
    "4. **Check secrets**: Streamlit Cloud → app → Settings → Secrets must "
    "contain the service account, COMPASS_SHEET_NAME, and GEMINI_API_KEY. The "
    "service account email must have access to COMPASS_CCSM (share the Sheet "
    "with it).\n"
    "5. **No data at all?** The agents write the tabs this app reads — check "
    "Agent Runs (To-Do & Health tab) and Apps Script triggers, not the app.":
        "1. **Borre la caché de datos** (botón de arriba). Resuelve el 90% de \"la hoja "
        "dice X pero la aplicación dice Y\" — las lecturas se guardan en caché por 5 "
        "minutos.\n"
        "2. **Restablezca la conexión con Sheets** si las lecturas fallan por completo.\n"
        "3. **Reinicie la aplicación**: Streamlit Cloud → menú ⋮ de la aplicación → "
        "Reboot. También fuerza el despliegue del último commit de `main`.\n"
        "4. **Revise los secretos**: Streamlit Cloud → aplicación → Settings → Secrets "
        "debe contener la cuenta de servicio, COMPASS_SHEET_NAME y GEMINI_API_KEY. El "
        "correo de la cuenta de servicio debe tener acceso a COMPASS_CCSM (comparta la "
        "hoja con él).\n"
        "5. **¿No hay datos en absoluto?** Los agentes escriben las pestañas que lee esta "
        "aplicación — revise las Ejecuciones de Agentes (pestaña Tareas y Estado) y los "
        "activadores de Apps Script, no la aplicación.",

    "1. Open COMPASS_CCSM → **Extensions → Apps Script → Triggers** (clock icon) "
    "and confirm each agent's time-driven trigger still exists.\n"
    "2. Check **Executions** in the same editor for red failed runs — the stack "
    "trace there is more detailed than AGENT_RUN_LOG.\n"
    "3. Remember **TEST_MODE**: if it's on (see above), all emails go to the "
    "test inbox — missionaries receiving nothing is expected.\n"
    "4. The Sunday chain is Agent1A → 1B → 1C; if 1A fails the whole chain "
    "stops. Start diagnosis at 1A.\n"
    "5. ⚠️ **Code changes**: editing `docs/*.gs` in the git repo does NOT change "
    "the live agents. Live code is only what's pasted into the Apps Script "
    "editor — every fix must be copy-pasted there by hand.":
        "1. Abra COMPASS_CCSM → **Extensiones → Apps Script → Activadores** (icono de "
        "reloj) y confirme que el activador por tiempo de cada agente todavía existe.\n"
        "2. Revise **Ejecuciones** en el mismo editor en busca de ejecuciones fallidas en "
        "rojo — el seguimiento de la pila ahí es más detallado que AGENT_RUN_LOG.\n"
        "3. Recuerde el **TEST_MODE**: si está activo (vea más arriba), todos los correos "
        "van a la bandeja de prueba — que los misioneros no reciban nada es lo esperado.\n"
        "4. La cadena del domingo es Agent1A → 1B → 1C; si 1A falla, toda la cadena se "
        "detiene. Empiece el diagnóstico en 1A.\n"
        "5. ⚠️ **Cambios de código**: editar `docs/*.gs` en el repositorio git NO cambia "
        "los agentes en vivo. El código en vivo es solo lo que se pega en el editor de "
        "Apps Script — cada corrección debe copiarse y pegarse ahí a mano.",

    # ══ f-string templates ══════════════════════════════════════════════════
    # Converted from f-strings, which are JoinedStr rather than Constant and so
    # were invisible to the extractor until it learned to read them. Keep every
    # {placeholder} spelled exactly as it appears in the key - t() formats after
    # lookup, and a renamed field falls back to English silently.

    # ── Page headers and section titles ──────────────────────────────────────
    "{mission_name} — PMG Compass": "{mission_name} — PMG Compass",
    "{mission_name} — Goals vs Actuals": "{mission_name} — Metas vs Reales",
    "{mission_name} — Searchable Notes with Follow-up Reminders":
        "{mission_name} — Notas con Búsqueda y Recordatorios de Seguimiento",
    "{mission_name} — weekly computed performance scores per area":
        "{mission_name} — puntajes de desempeño semanales calculados por área",
    "Teaching Pipeline — {scope_value}": "Proceso de Enseñanza — {scope_value}",
    "Form Submission Compliance — {scope_value}":
        "Cumplimiento de Envío de Formularios — {scope_value}",
    "Weekly Report Submission — {scope_value}":
        "Envío del Reporte Semanal — {scope_value}",
    "Key Indicators — {scope_value}": "Indicadores Clave — {scope_value}",
    "All Metrics — {scope_value}": "Todas las Métricas — {scope_value}",
    "{m_label} Trend — {scope_value}": "Tendencia de {m_label} — {scope_value}",
    "{m_label} by Area — {scope_value}": "{m_label} por Área — {scope_value}",
    "Mission Totals — {window_label}": "Totales de la Misión — {window_label}",
    "Mission Score — Average Across All Areas ({ms_range})":
        "Puntaje de la Misión — Promedio de Todas las Áreas ({ms_range})",
    "Effort Score Breakdown — {sel_area}":
        "Desglose del Puntaje de Esfuerzo — {sel_area}",
    "Areas of Concern — {metric_label}": "Áreas de Preocupación — {metric_label}",
    "Follow-ups Due — {count} note(s)":
        "Seguimientos Pendientes — {count} nota(s)",
    "Projected {proj_label} — Week ending {proj_date}":
        "{proj_label} Proyectado — Semana que termina el {proj_date}",
    "**Likely range:** {lower:g} – {upper:g}":
        "**Rango probable:** {lower:g} – {upper:g}",

    # ── Empty and info states ────────────────────────────────────────────────
    "No pipeline activity recorded for {scope_value} in {kpi_period}.":
        "No se registró actividad del proceso para {scope_value} en {kpi_period}.",
    "No snapshot metrics found for {scope_value}.":
        "No se encontraron métricas de instantánea para {scope_value}.",
    "No {scope_value} activity recorded for {kpi_period} — the sections below "
    "cover this period only.":
        "No se registró actividad de {scope_value} en {kpi_period} — las secciones "
        "de abajo cubren solo este período.",
    "No anomalies detected this week for **{metric_label}**.":
        "No se detectaron anomalías esta semana para **{metric_label}**.",
    "Not enough history yet for a trustworthy projection — need at least 4 "
    "completed weeks, have {have}.":
        "Aún no hay suficiente historial para una proyección confiable — se "
        "necesitan al menos 4 semanas completadas, hay {have}.",
    "Showing the {n} biggest drops of {total_flagged} areas flagged.":
        "Mostrando las {n} mayores caídas de {total_flagged} áreas marcadas.",
    "{n} area{value} flagged.": "{n} área{value} marcada(s).",
    "Areas where this week is below {threshold_pct}% of their 4-week average.":
        "Áreas cuyo valor de esta semana está bajo el {threshold_pct}% de su "
        "promedio de 4 semanas.",
    "Existing Entries ({count})": "Entradas Existentes ({count})",
    "{count} non-success run(s) in the last 14 days:":
        "{count} ejecución(es) sin éxito en los últimos 14 días:",

    # ── Maintenance snapshot ─────────────────────────────────────────────────
    "**Last Updated:** {last_updated}": "**Última Actualización:** {last_updated}",
    "**Current Week:** {week_start} — {week_end}":
        "**Semana Actual:** {week_start} — {week_end}",
    "**Total Areas:** {total_areas}": "**Total de Áreas:** {total_areas}",
    "**Python:** {value}  \n**Streamlit:** {streamlit}  \n**pandas:** {pandas} · "
    "**gspread:** {gspread}":
        "**Python:** {value}  \n**Streamlit:** {streamlit}  \n**pandas:** {pandas} · "
        "**gspread:** {gspread}",
    "**Mission flavor:** {id} ({display_name})  \n**Test mode:** {value}  \n"
    "**Signed in as:** {user} ({user2})":
        "**Variante de misión:** {id} ({display_name})  \n**Modo de prueba:** {value}  \n"
        "**Sesión iniciada como:** {user} ({user2})",
    "DAILY_LOG hasn't been written in {dl_age} days. The nightly ingestion "
    "likely failed — check the agent runs below and the Apps Script triggers.":
        "No se ha escrito en DAILY_LOG desde hace {dl_age} días. Probablemente falló "
        "la carga nocturna — revise las ejecuciones de agentes más abajo y los "
        "activadores de Apps Script.",
    "WEEKLY_KI's latest week ended {wk_age} days ago — a weekly cycle may have "
    "been missed.":
        "La última semana de WEEKLY_KI terminó hace {wk_age} días — puede que se "
        "haya omitido un ciclo semanal.",
    "COMPASS_CCSM link unavailable — {e}":
        "Enlace a COMPASS_CCSM no disponible — {e}",
    "Add to Knowledge Base as {next_id}":
        "Agregar a la Base de Conocimiento como {next_id}",
    "**Other / both forms** — {count} question(s)":
        "**Otros / ambos formularios** — {count} pregunta(s)",
    "{count} unsaved change(s). Saving updates QUESTIONS_CONFIG (agents follow "
    "it on their next run) — push to the Google Forms separately below.":
        "{count} cambio(s) sin guardar. Al guardar se actualiza QUESTIONS_CONFIG "
        "(los agentes lo siguen en su próxima ejecución) — envíe los cambios a "
        "Google Forms por separado más abajo.",
    "Metric key `{slug}` already exists — pick another.":
        "La clave de métrica `{slug}` ya existe — elija otra.",
    # One {week_of} placeholder, not {monday} {day}: the date is built by
    # app.i18n.formats.fmt_day_month now, so this string no longer has to
    # reassemble an English month abbreviation into Spanish word order — and
    # the month name itself is finally Spanish.
    "The weekly maintenance routine — week of {week_of}. Checkboxes reset "
    "each Monday and live in your browser session only; everything they ask "
    "about is verifiable further down this tab.":
        "La rutina de mantenimiento semanal — semana del {week_of}. Las "
        "casillas se reinician cada lunes y viven solo en la sesión de su navegador; "
        "todo lo que preguntan se puede verificar más abajo en esta pestaña.",

    # ── Goals page ───────────────────────────────────────────────────────────
    "Goals saved for **{selected_area}**.":
        "Metas guardadas para **{selected_area}**.",
    "Custom goals removed for **{selected_area}**.":
        "Metas personalizadas eliminadas para **{selected_area}**.",
    "Monthly goals saved for **{selected_area}** — {monthly_label}.":
        "Metas mensuales guardadas para **{selected_area}** — {monthly_label}.",
    "This will remove the custom goals row for **{selected_area}** and revert to "
    "mission-wide defaults. Are you sure?":
        "Esto eliminará la fila de metas personalizadas de **{selected_area}** y "
        "volverá a los valores predeterminados de la misión. ¿Está seguro?",
    "Mission goals saved. Last set by **{set_by}** · month of {month_label}":
        "Metas de la misión guardadas. Definidas por última vez por **{set_by}** · "
        "mes de {month_label}",
    "Last set by {set_by} · month of {ws_label}":
        "Definidas por última vez por {set_by} · mes de {ws_label}",
    "Preview — weekly goals ({count} areas)":
        "Vista previa — metas semanales ({count} áreas)",
    "Preview — monthly goals for {bulk_month_label}":
        "Vista previa — metas mensuales para {bulk_month_label}",
    "Recommended goals saved for **{count} areas** — weekly + "
    "{bulk_month_label} monthly.":
        "Metas recomendadas guardadas para **{count} áreas** — semanales + "
        "mensuales de {bulk_month_label}.",
    "Weekly goals saved for {count} areas, but monthly goals failed: {m_err}":
        "Metas semanales guardadas para {count} áreas, pero las metas mensuales "
        "fallaron: {m_err}",
    "Current nudge: **{current_nudge_pct}%**. Only the Mission President or "
    "Assistants can change it.":
        "Ajuste actual: **{current_nudge_pct}%**. Solo el Presidente de Misión o los "
        "Asistentes pueden cambiarlo.",
    "Active nudge: **{current_nudge_pct}%** — changes apply immediately; REC "
    "badges on the other tabs update the next time they render.":
        "Ajuste activo: **{current_nudge_pct}%** — los cambios se aplican de "
        "inmediato; los distintivos REC de las otras pestañas se actualizan la "
        "próxima vez que se muestran.",
    "Area override — applies only to {category}, ahead of any language category.":
        "Excepción de área — se aplica solo a {category}, con prioridad sobre "
        "cualquier categoría de idioma.",
    "\"{label}\" is already in the list.": "\"{label}\" ya está en la lista.",
    "\"{ovr_area}\" already has its own section above.":
        "\"{ovr_area}\" ya tiene su propia sección más arriba.",
    "{metric_labels} is already in this category.":
        "{metric_labels} ya está en esta categoría.",
    "{metric_labels}  ·  rec {rec:g}": "{metric_labels}  ·  rec {rec:g}",
    "REC {rec_value}": "REC {rec_value}",

    # ── Scores page ──────────────────────────────────────────────────────────
    "**Area Code:** `{cfg_area_code}`": "**Código de Área:** `{cfg_area_code}`",
    "Component mix must sum to 1.0 (currently {eff_sum:.4f}).":
        "La composición de componentes debe sumar 1.0 (actualmente {eff_sum:.4f}).",
    "Component mix sums to {eff_sum:.2f}":
        "La composición de componentes suma {eff_sum:.2f}",
    "Saved {saved} weight rows for {scope_txt}. The new weights take effect on "
    "the next scoring run (Sunday 11 PM MT, or run computeAllAreaScores() now).":
        "Se guardaron {saved} filas de pesos para {scope_txt}. Los nuevos pesos "
        "surten efecto en la próxima ejecución de puntajes (domingo 11 PM MT, o "
        "ejecute computeAllAreaScores() ahora).",
    "{scope_label}  |  {time_range}  |  {count} area(s) shown  |  Scores "
    "averaged across each area's weeks in this range":
        "{scope_label}  |  {time_range}  |  {count} área(s) mostradas  |  Puntajes "
        "promediados entre las semanas de cada área en este rango",

    # ── Action Center ────────────────────────────────────────────────────────
    "**{suggestions_ap_count} suggestion(s) at AP Approval**":
        "**{suggestions_ap_count} sugerencia(s) en Aprobación de los AP**",
    "**{suggestions_mp_count} suggestion(s) at Mission President Approval**":
        "**{suggestions_mp_count} sugerencia(s) en Aprobación del Presidente de Misión**",
    "**{followups_count} note follow-up(s) due**":
        "**{followups_count} seguimiento(s) de notas pendientes**",
    "**My Tasks — {count} open**": "**Mis Tareas — {count} abiertas**",
    "- **{task_name}** — assigned to {assigned_to} by {assigned_by}{due}":
        "- **{task_name}** — asignada a {assigned_to} por {assigned_by}{due}",
    "{task_name} — _assigned by {assigned_by}{due}_":
        "{task_name} — _asignada por {assigned_by}{due}_",
    "Task assigned to {name}.": "Tarea asignada a {name}.",
    "Visible to: {visible_to}": "Visible para: {visible_to}",
    "View {new_area}": "Ver {new_area}",
    "Note: {reviewer_note}": "Nota: {reviewer_note}",
    "**{label}** — {sum} of {count} active":
        "**{label}** — {sum} de {count} activas",

    # ── Finding Funnel ───────────────────────────────────────────────────────
    "{name} · {value:.1f} KB": "{name} · {value:.1f} KB",

    # ── Errors surfaced to the user ──────────────────────────────────────────
    "Could not read tab '{tab_name}': recent read failure, backing off before "
    "retrying.":
        "No se pudo leer la pestaña '{tab_name}': hubo una falla de lectura "
        "reciente, esperando antes de reintentar.",
    "Could not read tab '{tab_name}': {e}":
        "No se pudo leer la pestaña '{tab_name}': {e}",
    "Could not save to '{tab_name}': {e}":
        "No se pudo guardar en '{tab_name}': {e}",
    "Could not write AGENT_CONFIG: {e}": "No se pudo escribir AGENT_CONFIG: {e}",
    "Could not update AGENT_CONFIG: {e}": "No se pudo actualizar AGENT_CONFIG: {e}",
    "Could not write QUESTIONS_CONFIG: {e}":
        "No se pudo escribir QUESTIONS_CONFIG: {e}",
    "Could not write to KNOWLEDGE_BASE: {e}":
        "No se pudo escribir en KNOWLEDGE_BASE: {e}",
    "Failed to fetch goal: {e}": "No se pudo obtener la meta: {e}",
    "Failed to fetch goal history: {e}":
        "No se pudo obtener el historial de metas: {e}",
    "Failed to upsert goal: {e}": "No se pudo guardar la meta: {e}",
    "Failed to fetch area monthly goal: {e}":
        "No se pudo obtener la meta mensual del área: {e}",
    "Failed to upsert area monthly goal: {e}":
        "No se pudo guardar la meta mensual del área: {e}",
    "Failed to bulk upsert area monthly goals: {e}":
        "No se pudieron guardar en bloque las metas mensuales de las áreas: {e}",
    "Failed to read app setting {key!r}: {e}":
        "No se pudo leer la configuración {key!r}: {e}",
    "Failed to set app setting {key!r}: {e}":
        "No se pudo establecer la configuración {key!r}: {e}",
    "Failed to save: {err}": "No se pudo guardar: {err}",
    "Failed to save goals: {e}": "No se pudieron guardar las metas: {e}",
    "Failed to reset goals: {e}": "No se pudieron restablecer las metas: {e}",
    "Failed to save weekly goals: {e}":
        "No se pudieron guardar las metas semanales: {e}",
    "Failed to save monthly goals: {e}":
        "No se pudieron guardar las metas mensuales: {e}",
    "Failed to save monthly goals: {err}":
        "No se pudieron guardar las metas mensuales: {err}",
    "Failed to save nudge percentage: {nudge_save_error}":
        "No se pudo guardar el porcentaje de ajuste: {nudge_save_error}",
    "Failed to save config: {save_err}":
        "No se pudo guardar la configuración: {save_err}",
    "Push failed: {e}": "El envío falló: {e}",
    "Push failed: {data}": "El envío falló: {data}",

    # ── Informes (weekly mission report) ─────────────────────────────────────
    "Reports": "Informes",
    "{mission} — weekly mission report": "{mission} — informe semanal de la misión",
    "Scope": "Alcance",
    "Whole mission": "Toda la misión",
    "Week ending {week} · {scope} · {areas} area(s)":
        "Semana que termina el {week} · {scope} · {areas} área(s)",
    "No reported week yet. This page fills in once the weekly form has been "
    "submitted and the agents have written WEEKLY_KI.":
        "Aún no hay ninguna semana informada. Esta página se completa cuando "
        "se haya enviado el formulario semanal y los agentes hayan escrito "
        "WEEKLY_KI.",
    "Key Indicator": "Indicador Clave",
    "Achieved": "Logrado",
    "Goal set": "Meta fijada",
    "% of goal": "% de la meta",
    "No weekly Key Indicator data for this week and scope.":
        "No hay datos de Indicadores Clave para esta semana y alcance.",
    "No nightly data for this week.":
        "No hay datos diarios para esta semana.",
    "{start} to {end}": "{start} al {end}",
    "Week total": "Total de la semana",
    "Per area / day": "Por área / día",
    "No scores for this week yet. CCSM_AgentScores writes them on its weekly "
    "run.":
        "Aún no hay puntajes para esta semana. CCSM_AgentScores los escribe "
        "en su ejecución semanal.",
    "Skill": "Habilidad",
    "Effectiveness": "Efectividad",
    "Weekly Form Compliance": "Cumplimiento del Formulario Semanal",
    "Areas reporting": "Áreas que informaron",
    "Not reported": "Sin informar",
    "No areas in scope.": "No hay áreas en este alcance.",
    "{pct} of areas in scope submitted the weekly form.":
        "El {pct} de las áreas del alcance envió el formulario semanal.",
    "Areas with no weekly report ({count})":
        "Áreas sin informe semanal ({count})",
    "Export": "Exportar",
    "Download scores for this week (CSV)":
        "Descargar los puntajes de esta semana (CSV)",
    "Download Key Indicators for this week (CSV)":
        "Descargar los Indicadores Clave de esta semana (CSV)",
    "CSVs are written UTF-8 with a BOM so Excel opens the accents correctly.":
        "Los CSV se escriben en UTF-8 con BOM para que Excel abra bien los "
        "acentos.",

    # ── Traslados (transfer cycle) ───────────────────────────────────────────
    "Transfers": "Traslados",
    "Transfer": "Traslado",
    "Transfer {number}": "Traslado {number}",
    "Current transfer": "Traslado actual",
    "{mission} — the current transfer cycle":
        "{mission} — el ciclo de traslado actual",
    "No transfer has been scheduled yet. Fill in TRANSFER_SCHEDULE "
    "(Transfer_Number, Start_Date, Weeks, Status), or set "
    "TRANSFER_START_DATE in AGENT_CONFIG.":
        "Aún no se ha programado ningún traslado. Complete TRANSFER_SCHEDULE "
        "(Transfer_Number, Start_Date, Weeks, Status), o defina "
        "TRANSFER_START_DATE en AGENT_CONFIG.",
    "TRANSFER_SCHEDULE is empty, so this uses TRANSFER_START_DATE from "
    "AGENT_CONFIG and assumes a {weeks}-week cycle.":
        "TRANSFER_SCHEDULE está vacía, así que esto usa TRANSFER_START_DATE "
        "de AGENT_CONFIG y supone un ciclo de {weeks} semanas.",
    "Days elapsed": "Días transcurridos",
    "Days remaining": "Días restantes",
    "Weeks": "Semanas",
    "{start} to {end} · {weeks} weeks{status}":
        "{start} al {end} · {weeks} semanas{status}",
    "This transfer ended on {end} and no later one is scheduled. Add the next "
    "row to TRANSFER_SCHEDULE so the transfer-to-date figures below start "
    "counting from the right day.":
        "Este traslado terminó el {end} y no hay uno posterior programado. "
        "Agregue la siguiente fila a TRANSFER_SCHEDULE para que las cifras "
        "acumuladas del traslado empiecen a contar desde el día correcto.",
    "Full transfer schedule ({count})":
        "Calendario completo de traslados ({count})",
    "Starts": "Comienza",
    "Ends": "Termina",
    "Current": "Actual",
    "Area Performance This Transfer": "Desempeño por Área en Este Traslado",
    "Totals from the start of the transfer through today, as CCSM_Agent3 "
    "computes them into LIVE_SNAPSHOT. Non-numeric questions are left out — a "
    "running sum of a Sí/No or Todo/Algo answer means nothing.":
        "Totales desde el inicio del traslado hasta hoy, tal como "
        "CCSM_Agent3 los calcula en LIVE_SNAPSHOT. Se excluyen las preguntas "
        "no numéricas — sumar respuestas Sí/No o Todo/Algo no significa nada.",
    "LIVE_SNAPSHOT is empty. CCSM_Agent3 rebuilds it on each run from "
    "DAILY_LOG — check Agent Runs on the Mantenimiento page.":
        "LIVE_SNAPSHOT está vacía. CCSM_Agent3 la reconstruye en cada "
        "ejecución a partir de DAILY_LOG — revise Ejecuciones de Agentes en "
        "la página Mantenimiento.",
    "LIVE_SNAPSHOT has no transfer-to-date columns yet. They appear once the "
    "nightly agent has run against a populated DAILY_LOG.":
        "LIVE_SNAPSHOT aún no tiene columnas acumuladas del traslado. "
        "Aparecen cuando el agente diario se ejecuta sobre una DAILY_LOG con "
        "datos.",
    "Metrics": "Métricas",
    "Pick at least one metric.": "Elija al menos una métrica.",
    "Roster": "Nómina",
    "MISSION_ORG has no active areas.": "MISSION_ORG no tiene áreas activas.",
    "Areas": "Áreas",
    "Zones": "Zonas",
    "Districts": "Distritos",
    "Companion 1": "Compañero 1",
    "Companion 2": "Compañero 2",
    "Every area ({count})": "Todas las áreas ({count})",
    "All zones": "Todas las zonas",

    # ── Referencias (member referrals) ───────────────────────────────────────
    "Referrals": "Referencias",
    "{mission} — member referrals asked for and received":
        "{mission} — referencias de miembros solicitadas y recibidas",
    "This mission's nightly form does not ask about referrals, so there is "
    "nothing to report here. The questions this page needs are "
    "`references_asked` and `member_referrals_received` in QUESTIONS_CONFIG.":
        "El formulario diario de esta misión no pregunta por referencias, así "
        "que no hay nada que informar aquí. Las preguntas que necesita esta "
        "página son `references_asked` y `member_referrals_received` en "
        "QUESTIONS_CONFIG.",
    "No nightly data in this window yet. Referral figures appear once "
    "companionships submit the nightly form and the agents write DAILY_LOG.":
        "Aún no hay datos diarios en este período. Las cifras de referencias "
        "aparecen cuando las compañías envían el formulario diario y los "
        "agentes escriben DAILY_LOG.",
    "DAILY_LOG has no column for: {cols}. Those figures are left out rather "
    "than shown as zero.":
        "DAILY_LOG no tiene columna para: {cols}. Esas cifras se omiten en "
        "lugar de mostrarse como cero.",
    "Last {days} days": "Últimos {days} días",
    "{rate} of referrals asked for came back as a member referral ({received} "
    "from {asked} asks).":
        "El {rate} de las referencias solicitadas se convirtió en una "
        "referencia de un miembro ({received} de {asked} solicitudes).",
    "No referrals were asked for in this window, so there is no "
    "ask-to-referral rate to report ({received} referral(s) received).":
        "No se solicitaron referencias en este período, así que no hay una "
        "tasa de solicitud a referencia que informar ({received} "
        "referencia(s) recibida(s)).",
    "Referrals per day": "Referencias por día",
    "Rate": "Tasa",
    "Ranked by referrals received. An area that asked for none has no rate "
    "rather than a 0% one — it has not tried and failed, it has not tried.":
        "Ordenado por referencias recibidas. Un área que no solicitó ninguna "
        "no tiene tasa, en lugar de tener un 0% — no lo intentó y falló, "
        "simplemente no lo intentó.",
    "What this page counts": "Qué cuenta esta página",
    "- **{asked}** — how many times companionships asked a member for someone "
    "to teach, from the nightly form.\n- **{received}** — how many referrals "
    "members actually gave them, also from the nightly form.\n\nBoth are "
    "self-reported nightly counts, so they measure the conversation, not a "
    "record in another system. There is no referral feed to reconcile "
    "against.":
        "- **{asked}** — cuántas veces las compañías pidieron a un miembro "
        "alguien a quien enseñar, según el formulario diario.\n"
        "- **{received}** — cuántas referencias les dieron realmente los "
        "miembros, también del formulario diario.\n\nAmbas son cuentas "
        "diarias autoinformadas, así que miden la conversación, no un "
        "registro en otro sistema. No hay un flujo de referencias con el cual "
        "conciliarlas.",

    # ── Editar Envíos (corrections to DAILY_LOG / WEEKLY_KI) ─────────────────
    "Edit Submissions": "Editar Envíos",
    "Correct a report a companionship already submitted":
        "Corrija un informe que una compañía ya envió",
    "Corrections are written to DAILY_LOG and WEEKLY_KI — the tabs the "
    "dashboard and the agents both read — not to the Google Forms response "
    "sheets, which the agents do not re-read. Every change is recorded in "
    "AUDIT_LOG with your address.":
        "Las correcciones se escriben en DAILY_LOG y WEEKLY_KI — las pestañas "
        "que leen tanto el panel como los agentes — y no en las hojas de "
        "respuestas de Google Forms, que los agentes no vuelven a leer. Cada "
        "cambio queda registrado en AUDIT_LOG con su dirección.",
    "Which report": "Qué informe",
    "Nightly report": "Informe diario",
    "Weekly report (Key Indicators)": "Informe semanal (Indicadores Clave)",
    "Week ending": "Semana que termina",
    "No active areas found in MISSION_ORG.":
        "No se encontraron áreas activas en MISSION_ORG.",
    "{tab} has no columns yet, so there is nothing to correct. The agents "
    "create it on their first successful run — check Agent Runs on the "
    "Mantenimiento page.":
        "{tab} aún no tiene columnas, así que no hay nada que corregir. Los "
        "agentes la crean en su primera ejecución exitosa — revise "
        "Ejecuciones de Agentes en la página Mantenimiento.",
    "— a date not reported (backfill) —":
        "— una fecha no informada (completar) —",
    "Backfilling creates a row that was never submitted. The nightly agent "
    "skips any date already present, so once this is saved the companionship's "
    "own late submission for that date will NOT replace it. Only use this when "
    "the report will never arrive.":
        "Completar crea un registro que nunca fue enviado. El agente diario "
        "omite toda fecha que ya exista, así que una vez guardado esto, el "
        "envío tardío de la propia compañía para esa fecha NO lo reemplazará. "
        "Úselo solo cuando el informe nunca vaya a llegar.",
    "Date to create": "Fecha que se creará",
    "Pick a date to continue.": "Elija una fecha para continuar.",
    "No report found for {area} on {date}.":
        "No se encontró un informe de {area} para el {date}.",
    "Currently recorded — {area}, {date}":
        "Registrado actualmente — {area}, {date}",
    "New values": "Valores nuevos",
    "Only the fields you change are written. Everything left alone keeps the "
    "value the companionship reported.":
        "Solo se escriben los campos que usted cambie. Todo lo demás conserva "
        "el valor que informó la compañía.",
    "No changes yet.": "Aún no hay cambios.",
    "{count} field(s) changed: {fields}":
        "{count} campo(s) modificado(s): {fields}",
    "Save correction": "Guardar corrección",
    "Create this report": "Crear este informe",
    "Saved {count} field(s) for {area} on {date}. The change reaches the rest "
    "of the dashboard on the agents' next run.":
        "Se guardaron {count} campo(s) de {area} para el {date}. El cambio "
        "llega al resto del panel en la próxima ejecución de los agentes.",
    "Full record as stored": "Registro completo tal como está guardado",
    "Field": "Campo",

    # KPI card captions. These live inside an f-string HTML block in
    # design_system.render_kpi_row, so the string extractor cannot see them —
    # they were plain English on every page, in both languages, until routed
    # through t() by hand.
    "{pct}% of {goal} goal": "{pct}% de la meta de {goal}",
    "{pct}% of {expectation} expectation": "{pct}% de la expectativa de {expectation}",

    # ── Phase 2 de-contamination: Dashboard + Scores rebuilt sections ────────
    # New strings from replacing Provo-keyed sections with catalogue-driven
    # ones (Dashboard KPI/KI rows and trend charts, Scores' Daily Activity).
    "Count": "Cantidad",
    "Date": "Fecha",
    "Week Ending": "Semana que termina",
    "Nightly Activity": "Actividad diaria",
    "Nightly Activity — Last 7 Days": "Actividad diaria — últimos 7 días",
    "Daily Trend": "Tendencia diaria",
    "Daily Trend — Last 7 Days": "Tendencia diaria — últimos 7 días",
    "Daily {metric} — Last 7 Days": "{metric} por día — últimos 7 días",
    "{metric} per day (mission total)": "{metric} por día (total de la misión)",
    "By Area": "Por área",
    "Metrics to chart": "Métricas para graficar",
    "Pick at least one metric to chart.": "Elija al menos una métrica para graficar.",
    "Nightly reporting — {window_label}": "Informes diarios — {window_label}",
    "DAILY_LOG has no Date column, so there is no trend to draw.":
        "DAILY_LOG no tiene columna Date, por lo que no hay tendencia que graficar.",
    "DAILY_LOG has no Area column, so it cannot be broken down by area.":
        "DAILY_LOG no tiene columna Area, por lo que no se puede desglosar por área.",
    "None of this mission's nightly metrics appear in DAILY_LOG. Check the "
    "QUESTIONS_CONFIG tab of COMPASS_CCSM, then re-run the nightly refresh.":
        "Ninguna de las métricas diarias de esta misión aparece en DAILY_LOG. "
        "Revise la pestaña QUESTIONS_CONFIG de COMPASS_CCSM y vuelva a ejecutar "
        "la actualización diaria.",
    "No metrics are configured for this mission, so there is nothing to "
    "weight. Check the QUESTIONS_CONFIG and SCORE_CONFIG tabs of "
    "COMPASS_CCSM before editing score weights.":
        "Esta misión no tiene métricas configuradas, así que no hay nada que "
        "ponderar. Revise las pestañas QUESTIONS_CONFIG y SCORE_CONFIG de "
        "COMPASS_CCSM antes de editar los pesos del puntaje.",
    "Weekly-form Key Indicators. Metrics left at 0 don't count toward KI.":
        "Indicadores Clave del formulario semanal. Las métricas en 0 no cuentan "
        "para el puntaje de Indicadores Clave.",
    "Full Effort": "Todo el esfuerzo",
    "Effort reported per day": "Esfuerzo informado por día",
    "No effort responses recorded for this window yet.":
        "Aún no hay respuestas de esfuerzo registradas para este período.",

    # QUESTIONS_CONFIG Data_Type values. Display only — format_func translates
    # what is shown while the raw English value is what gets written to the
    # sheet and read by the agents.
    "NUMBER": "NÚMERO",
    "YESNO": "SÍ/NO",
    "CHOICE": "OPCIÓN",
    "e.g. Contactos": "p. ej. Contactos",
    "e.g. Contactos con amigos": "p. ej. Contactos con amigos",

    "REC is a light stretch goal — about {get_rec_stretch_pct}% above this "
    "area's all-time weekly average — to nudge the area to do slightly better. "
    "Any metric with an expectation saved in Area Expectation Settings shows "
    "goal / this area's weekly expectation — add or change one there and the "
    "fraction follows the moment it's saved.":
        "REC es una meta de estiramiento leve — alrededor de un "
        "{get_rec_stretch_pct}% por encima del promedio semanal histórico de "
        "esta área — para motivarla a mejorar un poco. Toda métrica con una "
        "expectativa guardada en Configuración de Expectativas por Área muestra "
        "meta / la expectativa semanal de esta área; agregue o cambie una allí "
        "y la fracción se actualiza apenas se guarda.",

    # ── Long help texts (metric names and code identifiers left as-is) ───────
    # The weight list is now a {weights} placeholder built from SCORE_CONFIG at
    # render time — it used to be spelled out here as Provo's "nm_lessons 30% ·
    # new_found 25% · mmm_sent 20% · pew 15% · gate 10%", in BOTH languages, so
    # the Spanish page stated Provo's weights as fact about a CCSM area.
    "Each slice is that metric's average share of this area's weekly Effort "
    "score across {count} week(s) in {time_range} (actual vs. expectation, "
    "weighted {weights}) — not raw activity volume.":
        "Cada porción es la participación promedio de esa métrica en el puntaje "
        "semanal de Esfuerzo de esta área a lo largo de {count} semana(s) en "
        "{time_range} (real vs. expectativa, ponderado {weights}) — no el "
        "volumen bruto de actividad.",

    "Mission average: **{avg:.1f}/week** · projected goal at **{proj_pct}%** "
    "nudge: **{proj_goal}/week**. The green line is what the mission-wide REC "
    "badge recommends at the current slider position; per-area REC badges use "
    "the same math on each area's own history.":
        "Promedio de la misión: **{avg:.1f}/semana** · meta proyectada con un ajuste "
        "de **{proj_pct}%**: **{proj_goal}/semana**. La línea verde es lo que "
        "recomienda el distintivo REC de toda la misión en la posición actual del "
        "control; los distintivos REC por área usan el mismo cálculo sobre el "
        "historial de cada área.",

    "Recommended goals computed for **{count} areas** — each area's own REC "
    "values, exactly what the per-metric REC pills show. Review below, then "
    "**Save All Recommended** to write every area's weekly goals and its "
    "{bulk_month_label} monthly goals. This overwrites any custom goals already "
    "saved.":
        "Metas recomendadas calculadas para **{count} áreas** — los valores REC "
        "propios de cada área, exactamente los que muestran las píldoras REC de cada "
        "métrica. Revíselas abajo y luego use **Guardar Todo lo Recomendado** para "
        "escribir las metas semanales de cada área y sus metas mensuales de "
        "{bulk_month_label}. Esto sobrescribe cualquier meta personalizada ya "
        "guardada.",

    "REC is a light stretch goal — about {get_rec_stretch_pct}% above this "
    "area's all-time weekly average — to nudge the area to do slightly better. "
    "Any metric with an expectation saved in Area Expectation Settings shows "
    "goal / this area's weekly expectation — add or change one there and the "
    "fraction follows the moment it's saved. Fellowshipped Lessons (formerly "
    "Member Lessons) shows goal / this area's own NM Lessons goal, live as you "
    "type it above (unless it's given its own expectation, which then wins). "
    "LSI Follow-Ups shows goal / this area's own LSI Given goal the same way, "
    "so you can see how many of the LSIs given are actually being followed up on.":
        "REC es una meta de superación leve — alrededor de {get_rec_stretch_pct}% por "
        "encima del promedio semanal histórico de esta área — para animarla a mejorar "
        "un poco. Cualquier métrica con una expectativa guardada en Configuración de "
        "Expectativas por Área muestra meta / la expectativa semanal de esta área — "
        "agregue o cambie una ahí y la fracción se actualiza apenas se guarde. "
        "Lecciones con Acompañamiento (antes Lecciones con Miembro) muestra meta / la "
        "propia meta de Lecciones NM de esta área, en vivo mientras la escribe arriba "
        "(salvo que tenga su propia expectativa, que entonces prevalece). Seguimientos "
        "de LSI muestra meta / la propia meta de LSI Impartidas de esta área del mismo "
        "modo, para que vea a cuántas de las LSI impartidas se les está dando "
        "seguimiento.",

    "Key indicators for **{monthly_label}**, in order: Gate, Date, New, Pew, "
    "Renew, Mate. REC is a light stretch goal — about {get_rec_stretch_pct}% "
    "above this area's own real average monthly performance (every completed "
    "calendar month in this area's history, not a weekly number scaled up). Any "
    "indicator with an expectation saved in Area Expectation Settings shows "
    "goal / that expectation sized to this month — a monthly figure as-is, a "
    "weekly one times this month's exact weeks (Renew, a Sunday-only event, "
    "times its actual Sunday count). Two fallbacks when no expectation is set: "
    "Renew shows goal / the MAX possible Recent-Convert attendances this month "
    "— every recent convert, every Sunday they were eligible for (a convert "
    "baptized mid-month only counts for the Sundays after their baptism, not "
    "the ones before) — and Mate shows goal / this area's own hypothetical "
    "monthly Non-Member Lesson target (its NM Lessons expectation scaled to "
    "this month), not based on actual data. New and Mate also appear above "
    "under Nightly Form Goals as a separate WEEKLY number — the two boxes are "
    "independent, not kept in sync.":
        "Indicadores clave de **{monthly_label}**, en orden: Gate, Date, New, Pew, "
        "Renew, Mate. REC es una meta de superación leve — alrededor de "
        "{get_rec_stretch_pct}% por encima del propio promedio mensual real de esta "
        "área (cada mes calendario completado en el historial de esta área, no una "
        "cifra semanal escalada). Cualquier indicador con una expectativa guardada en "
        "Configuración de Expectativas por Área muestra meta / esa expectativa "
        "ajustada a este mes — una cifra mensual tal cual, una semanal multiplicada "
        "por las semanas exactas de este mes (Renew, un evento solo dominical, por su "
        "cantidad real de domingos). Dos alternativas cuando no hay expectativa: Renew "
        "muestra meta / el MÁXIMO posible de asistencias de conversos recientes este "
        "mes — cada converso reciente, cada domingo en que era elegible (un converso "
        "bautizado a mitad de mes solo cuenta para los domingos posteriores a su "
        "bautismo, no los anteriores) — y Mate muestra meta / el objetivo mensual "
        "hipotético de Lecciones a No Miembros de esta área (su expectativa de "
        "Lecciones NM ajustada a este mes), no basado en datos reales. New y Mate "
        "también aparecen arriba en Metas del Formulario Nocturno como una cifra "
        "SEMANAL aparte — las dos casillas son independientes y no se sincronizan.",

    "REC is a light stretch goal — about {get_rec_stretch_pct}% above the whole "
    "mission's typical MONTHLY performance across every area, for a month this "
    "length — to nudge the mission to do slightly better. Church-attendance "
    "indicators scale by the number of Sundays this month, since attendance is "
    "a once-a-week event, rather than the general weeks-in-month figure used "
    "for other metrics. Any goal whose indicator has expectations saved in Area "
    "Expectation Settings shows goal / a hypothetical mission-wide target for "
    "this month — every area at its own expectation, summed and sized to this "
    "month's exact length — not based on actual data. A goal with no "
    "expectation saved shows no fraction at all.":
        "REC es una meta de superación leve — alrededor de {get_rec_stretch_pct}% por "
        "encima del desempeño MENSUAL típico de toda la misión en todas las áreas, "
        "para un mes de esta duración — para animar a la misión a mejorar un poco. Los "
        "indicadores de asistencia a la Iglesia se ajustan según la cantidad de "
        "domingos de este mes, ya que la asistencia es un evento semanal, en lugar de "
        "la cifra general de semanas del mes que se usa para otras métricas. Cualquier "
        "meta cuyo indicador tenga expectativas guardadas en Configuración de "
        "Expectativas por Área muestra meta / un objetivo hipotético de toda la misión "
        "para este mes — cada área con su propia expectativa, sumadas y ajustadas a la "
        "duración exacta de este mes — no basado en datos reales. Una meta sin "
        "expectativa guardada no muestra ninguna fracción.",

    "{span}  |  {kpi_period}  |  every question this area has ever reported, "
    "totalled for this period (daily + weekly Sunday form; rates excluded — see "
    "the Metric picker below for a single metric's trend)":
        "{span}  |  {kpi_period}  |  cada pregunta que esta área haya reportado "
        "alguna vez, totalizada para este período (formulario diario + semanal "
        "dominical; se excluyen las tasas — vea el selector de Métrica más abajo para "
        "la tendencia de una métrica individual)",

    # Found moved from the nightly log to the weekly Key Indicators along with
    # the other two — see the funnel's source note in app/breakdowns_engine.py.
    "{span}  |  {kpi_period} — counts what happened in this period. Found, "
    "At Sacrament and Baptized from the weekly Key Indicators, Taught from the "
    "Tableau export; the bars come from different reports and aren't subsets "
    "of each other.":
        "{span}  |  {kpi_period} — cuenta lo que ocurrió en este período. "
        "Encontradas, En Sacramental y Bautizadas provienen de los Indicadores "
        "Clave semanales, y Enseñadas de la exportación de Tableau; las barras "
        "provienen de reportes distintos y no son subconjuntos entre sí.",

    # ── 12_Traslados.py — Apply a Transfer (added 2026-08-05) ────────────────
    "Apply a Transfer": "Aplicar un Traslado",
    "Applying a transfer is available to mission leadership only.":
        "Aplicar un traslado está disponible solo para el liderazgo de la misión.",
    "Pull the current roster from IMOS, preview what would change in "
    "MISSION_ORG, then apply it. Each step needs a separate click — nothing "
    "here runs automatically.":
        "Extraiga la organización actual desde IMOS, previsualice qué "
        "cambiaría en MISSION_ORG y luego apliquelo. Cada paso requiere un "
        "clic por separado — nada aquí ocurre automáticamente.",
    "TRANSFER_IMPORT is empty. Pull the roster first (below), or paste "
    "it into the TRANSFER_IMPORT tab by hand.":
        "TRANSFER_IMPORT está vacío. Extraiga primero la organización (abajo), "
        "o péguela manualmente en la pestaña TRANSFER_IMPORT.",
    "TRANSFER_IMPORT has {count} rows.": "TRANSFER_IMPORT tiene {count} filas.",
    "1 · Preview": "1 · Previsualizar",
    "Reading MISSION_ORG and TRANSFER_IMPORT...":
        "Leyendo MISSION_ORG y TRANSFER_IMPORT...",
    "{roster} roster rows vs {org} MISSION_ORG rows.":
        "{roster} filas de organización vs {org} filas de MISSION_ORG.",
    "New areas": "Áreas nuevas",
    "Deactivating": "Desactivando",
    "Changed": "Modificadas",
    "Reactivating": "Reactivando",
    "Override the deactivation guard (only if this many deactivations "
    "is genuinely correct)":
        "Anular el límite de desactivación (solo si esta cantidad de "
        "desactivaciones es realmente correcta)",
    "2 · Apply": "2 · Aplicar",
    "Applying to MISSION_ORG...": "Aplicando a MISSION_ORG...",
    "Applied.": "Aplicado.",
    "New areas need an email address added by hand: {areas}":
        "Las áreas nuevas necesitan que se agregue un correo manualmente: {areas}",
    "3 · Sync nightly + weekly form dropdowns":
        "3 · Sincronizar los menús de los formularios diario y semanal",
    "Syncing form dropdowns...": "Sincronizando los menús de los formularios...",

    # ── 12_Traslados.py — cloud Pull button + app/components/cloud_job_ui.py
    # (added 2026-08-05) ──────────────────────────────────────────────────
    "0 · Pull roster from IMOS (cloud)":
        "0 · Extraer organización desde IMOS (nube)",
    "Pulling the roster from IMOS...": "Extrayendo la organización desde IMOS...",
    "Roster pulled. Click Preview to see the diff.":
        "Organización extraída. Haga clic en Previsualizar para ver los cambios.",
    "Working...": "Trabajando...",
    "{status_text} ({elapsed} elapsed)": "{status_text} ({elapsed} transcurrido)",
    "Cloud job failed: {summary}": "El trabajo en la nube falló: {summary}",
    "{error} — check the GitHub Actions tab; it may still finish.":
        "{error} — revise la pestaña de GitHub Actions; podría terminar todavía.",

    # ── 12_Traslados.py — Schedule/Roster Update tabs + checklist +
    # Emergency update (added 2026-08-06) ────────────────────────────────
    "**Transfer day checklist**\n"
    "1. **Pull roster from IMOS** — wait for the success message.\n"
    "2. **Preview** — review New/Deactivating/Changed/Reactivating below; "
    "tick the override box only if the guard blocks Apply and the number "
    "of deactivations is genuinely correct for this transfer.\n"
    "3. **Apply** — updates MISSION_ORG.\n"
    "4. **Sync forms** — updates the nightly/weekly dropdowns; run this "
    "after Apply.":
        "**Lista de verificación del día de traslado**\n"
        "1. **Extraer organización desde IMOS** — espere el mensaje de éxito.\n"
        "2. **Previsualizar** — revise Áreas nuevas/Desactivando/Modificadas/"
        "Reactivando abajo; marque la casilla de anulación solo si el "
        "límite bloquea Aplicar y la cantidad de desactivaciones es "
        "realmente correcta para este traslado.\n"
        "3. **Aplicar** — actualiza MISSION_ORG.\n"
        "4. **Sincronizar formularios** — actualiza los menús diario y "
        "semanal; hágalo después de Aplicar.",
    "4 · Emergency update (pull + apply)":
        "4 · Actualización de emergencia (extraer + aplicar)",
    "One click for a mid-cycle move: pulls the roster, then applies it "
    "immediately — skipping the review step above. Run **3 · Sync forms** "
    "separately afterward if the form dropdowns need updating.":
        "Un clic para un cambio a mitad de ciclo: extrae la organización y "
        "la aplica de inmediato — sin pasar por la revisión de arriba. "
        "Ejecute **3 · Sincronizar formularios** por separado después si "
        "los menús de los formularios necesitan actualizarse.",
    "Tip: run 1 · Preview above first if you want to review the diff "
    "before it's applied — this button applies right away, showing you "
    "what changed only after the fact.":
        "Consejo: ejecute primero 1 · Previsualizar arriba si desea "
        "revisar los cambios antes de aplicarlos — este botón aplica de "
        "inmediato y muestra lo que cambió recién después.",
    "4 · Run emergency update": "4 · Ejecutar actualización de emergencia",
    "Step 1/2 — pulling roster...": "Paso 1/2 — extrayendo la organización...",
    "Pull failed — stopped before apply.\n\n{error}":
        "La extracción falló — se detuvo antes de aplicar.\n\n{error}",
    "Step 2/2 — applying transfer...": "Paso 2/2 — aplicando el traslado...",
    "Apply blocked by the guard: {error}\n\nUse 1 · Preview and 2 · Apply "
    "above to review and override.":
        "Aplicar fue bloqueado por el límite: {error}\n\nUse 1 · "
        "Previsualizar y 2 · Aplicar arriba para revisar y anular.",
    "Emergency update failed after pull: {error}":
        "La actualización de emergencia falló después de extraer: {error}",
    "Emergency update complete.": "Actualización de emergencia completa.",
}
