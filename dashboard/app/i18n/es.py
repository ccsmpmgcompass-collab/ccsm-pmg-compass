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
}
