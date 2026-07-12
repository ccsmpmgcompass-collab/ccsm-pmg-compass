# PMG Compass — New Mission Setup Guide
## Hyper-Detailed Runbook | First Use: Chile Concepción South Mission (CCSM)

> **How to use this guide:** Follow every numbered step in order. Steps marked 🔁 **REUSABLE** are the exact same for every future mission — just swap in new values. Steps marked ⚠️ **ONE-TIME** only need to happen once (they permanently upgrade the codebase so future missions are easier).

---

## Prerequisites Checklist (complete before starting)

Before you begin, make sure you have:
- [ ] Access to the PMG-Compass GitHub repo (you can push to `main`)
- [ ] The `COMPASS_Main` Google Sheet open (Utah Provo Mission, current production sheet)
- [ ] Google Workspace admin access to `pmg.compass@gmail.com`
- [ ] Streamlit Cloud account logged in (as the account that owns the current deployment)
- [ ] Python environment on your PC with the repo dependencies installed (`pip install -r requirements.txt`)
- [ ] The intake information for CCSM filled in (see Step 1 — the form will collect this)
- [ ] Node: estimated time for the full process is ~10–14 hours of work spread over several days

---

## STEP 1 — Create the Mission Intake Google Form
### 🔁 REUSABLE — Run this for every new mission

This form is what you send to new Mission Presidents or tech missionaries before you build anything. Their answers drive every downstream decision (which stats to track, which language to use, timezone, start date, etc.).

### 1.1 — Go to Google Forms and create a new blank form

1. Go to [forms.google.com](https://forms.google.com) while logged in as `pmg.compass@gmail.com`
2. Click the **"+"** (Blank) button to create a new form
3. Click the form title at the top ("Untitled form") and type: `PMG Compass — New Mission Setup`
4. Click the form description area and type:
   ```
   Welcome! This form collects the information we need to set up PMG Compass for your mission.
   Please fill this out completely. If you are unsure about any answer, leave a note in the
   Contact Info question and we will follow up.
   ```

### 1.2 — Add the 8 required questions (in this exact order)

**Question 1: Mission Name**
- Click the question and type: `What is the full official name of your mission?`
- Change type to **Short answer**
- Turn on **Required**
- Example hint text (click the "i" icon): `e.g., Chile Concepción South Mission`

**Question 2: Dashboard Language**
- Click the "+" to add a question
- Type: `What language should the leadership dashboard be displayed in?`
- Change type to **Multiple choice**
- Add options (click "Add option" for each):
  - English
  - Spanish
  - Portuguese
  - French
  - Other (please specify in Contact Info)
- Turn on **Required**

**Question 3: Missionary Communication Language**
- Add a question: `What language should missionary-facing emails and forms be in?`
- Type: **Multiple choice**
- Same options as Question 2: English / Spanish / Portuguese / French / Other
- Turn on **Required**

**Question 4: Mission Timezone**
- Add a question: `What is the primary timezone of your mission?`
- Type: **Dropdown**
- Add these options (copy/paste each):
  - America/Denver (Utah/Mountain Time)
  - America/Santiago (Chile)
  - America/Sao_Paulo (Brazil East)
  - America/Manaus (Brazil West)
  - America/Lima (Peru)
  - America/Bogota (Colombia)
  - America/Mexico_City (Mexico Central)
  - America/Los_Angeles (Pacific US)
  - America/Chicago (Central US)
  - America/New_York (Eastern US)
  - America/Phoenix (Arizona)
  - Europe/London (UK)
  - Europe/Madrid (Spain)
  - Pacific/Auckland (New Zealand)
  - Asia/Manila (Philippines)
- Turn on **Required**

**Question 5: Wanted Start Date**
- Add a question: `When do you want missionaries to start submitting reports?`
- Type: **Date**
- Description text: `This is the first date missionaries will fill out the nightly form.`
- Turn on **Required**

**Question 6: Role**
- Add a question: `What is your role in the mission?`
- Type: **Multiple choice**
- Options:
  - Mission President
  - Assistant to the President (AP)
  - Zone Leader
  - District Leader
  - Tech Missionary
  - Mission Office Staff
  - Other
- Turn on **Required**

**Question 7: Contact Info**
- Add a question: `Your name, email address, and phone number`
- Type: **Paragraph**
- Description: `Include the Mission President's email even if someone else is filling out this form.`
- Turn on **Required**

**Question 8: Daily Form Stats (choose 10–25)**
- Add a question: `Which statistics should missionaries report DAILY? Choose 10 to 25.`
- Type: **Checkboxes**
- Add all 50 options below (copy/paste each one):

```
New People Found
Non-member Doors Attempted
Non-members Contacted
NM Meaningful Conversations
NM Texts Sent
Social Media Messages Sent
Phone Calls to Non-Members
Online Referrals Received
Member Referrals Today
Media Referrals Received
Street Contacts Made
Non-member Lessons
Lessons with Member Present
Recent Convert Lessons
Less Active Lessons
First Lesson Taught (Lesson 1)
Restoration Presentation Given (Lesson 2)
Plan of Salvation Discussion (Lesson 3)
Gospel of Jesus Christ Discussion (Lesson 4)
Laws and Ordinances Discussion (Lesson 5)
Ward Members Given LSI (Love/Share/Invite)
LSI Follow-Ups Made
Ward Mission Leader Contacted
Fellowshipper Arranged
Auxiliary Coordination Attempt
Quorum/Relief Society Coordination Attempt
Ward Member Contacts Made
Baptismal Date Set
Church Invite Given
Prayer Commitment Made
Book of Mormon Shared
Investigators at Church
Baptismal Interview Completed
Baptism Performed
Confirmation Performed
Less Active Members Attempted
Recent Convert Check-in Completed
LOCOS Attempt
Less Active at Church This Week
MMMs Sent (Member Missionary Messages)
Informational Attempt
Service Hours (# of hours)
Language Study (minutes)
Splits/Exchanges Arranged
Mission Leadership Contacted
Devotional or Meeting Attended
Effort Level (All/Most/Some)
Daily Journal Written
District Coordinator Contacted
Other (describe in Contact Info)
```

- Add a validation rule: click the three-dot menu (⋮) at bottom-right of the question → **Response validation** → **Select at least** → type `10` with the error message: `Please select at least 10 stats.`
- Add another rule: **Select at most** → `25` with message: `Please select no more than 25 stats.`
- Turn on **Required**

**Question 9: Weekly Key Indicators (choose 3–10)**
- Add a question: `Which statistics should missionaries report WEEKLY? These are the big "Key Indicators."`
- Type: **Checkboxes**
- Options:
```
Potential Members at Sacrament Meeting (Pew)
Friends on a Baptismal Date (Date)
Baptized and Confirmed (Gate)
Recent Converts at Church This Week (Renew)
RC Who Could Have Attended This Week (Total)
Total NM Lessons for the Week
Total New People Found for the Week
Total Contacts Made for the Week
Total Online Referrals for the Week
Total Member Referrals for the Week
Investigators Progressing Toward Baptism
Zone Goal Achievement %
```
- Add validation: Select at least 3 / at most 10
- Turn on **Required**

### 1.3 — Configure form settings

1. Click the **gear icon** (Settings) at the top right
2. Under **Responses**: Check "Collect email addresses" → set to "Responder input" (not verified)
3. Under **Presentation**: Check "Show progress bar" — useful since form is long
4. Click **Save**

### 1.4 — Share the form

1. Click the **Send** button (top right, purple)
2. Click the link icon (🔗)
3. Check "Shorten URL"
4. Copy the link and send it to the CCSM Mission President or tech contact

### 1.5 — Connect responses to a tracking sheet

1. Click the **Responses** tab in the form
2. Click the Google Sheets icon (green spreadsheet)
3. Click "Create a new spreadsheet"
4. Name it: `PMG Compass — Mission Intake Responses`
5. This sheet is your intake dashboard — each row is one mission's setup data

> **Future missions:** Just send this same form link again. Each new response appears as a new row. You don't need to recreate the form.

---

## STEP 2 — Code Changes: Multi-Mission Config Foundation
### ⚠️ ONE-TIME — Do this once, benefits all future missions

Currently "Utah Provo Mission" is hardcoded in ~25 places in the code. After this step, the codebase reads the mission name from the Google Sheet's config tab — meaning ANY mission can have its own name/language/timezone just by updating their sheet.

### 2.1 — Add mission config keys to the current COMPASS_Main sheet

1. Open `COMPASS_Main` Google Sheet
2. Click the `AGENT_CONFIG` tab
3. Find the bottom of the existing key-value rows
4. Add these new rows (Column A = key, Column B = value):

| Key (Column A) | Value (Column B) |
|---|---|
| `MISSION_NAME` | `Utah Provo Mission` |
| `MISSION_LANGUAGE` | `EN` |
| `MISSION_TIMEZONE` | `America/Denver` |
| `MISSION_LOCALE` | `en_US` |

5. Save. These are the existing mission's values — adding them now doesn't change anything, just makes them config-driven.

### 2.2 — Create `app/config/mission.py`

In VS Code (or any editor), create a new file at: `C:\Users\2011794-MTS\Desktop\PMG-Compass\app\config\mission.py`

Paste this exact content:

```python
import streamlit as st
from app.db.sheets_client import read_tab


@st.cache_data(ttl=3600)
def _load_mission_config() -> dict:
    try:
        df = read_tab("AGENT_CONFIG")
        config = dict(zip(df.iloc[:, 0], df.iloc[:, 1]))
        return config
    except Exception:
        return {}


def get_mission_name() -> str:
    return _load_mission_config().get("MISSION_NAME", "PMG Compass")


def get_mission_language() -> str:
    return _load_mission_config().get("MISSION_LANGUAGE", "EN").upper()


def get_mission_timezone() -> str:
    return _load_mission_config().get("MISSION_TIMEZONE", "America/Denver")


def get_mission_locale() -> str:
    return _load_mission_config().get("MISSION_LOCALE", "en_US")
```

### 2.3 — Create `app/utils/strings.py`

Create a new file at: `C:\Users\2011794-MTS\Desktop\PMG-Compass\app\utils\strings.py`

Paste this content (this is the English base — Spanish will be added in Step 3):

```python
from app.config.mission import get_mission_language

_STRINGS = {
    "EN": {
        # --- Metric labels ---
        "metric_nm_lessons": "NM Lessons",
        "metric_member_lessons": "Member Lessons",
        "metric_rc_lessons": "RC Lessons",
        "metric_la_lessons": "Less Active Lessons",
        "metric_lsi_given": "LSI Given",
        "metric_lsi_followups": "LSI Follow-Ups",
        "metric_new_found": "New People Found",
        "metric_online_referrals": "Online Referrals",
        "metric_nm_doors": "NM Doors Attempt",
        "metric_nm_contacted": "NM Contacted",
        "metric_nm_meaningful": "NM Meaningful Convos",
        "metric_mmm_sent": "MMMs Sent",
        "metric_la_attempt": "LA Members Attempt",
        "metric_fellowshipper_attempt": "Fellowshipper Attempt",
        "metric_aux_attempt": "Aux/Coord Attempt",
        "metric_info_attempt": "Informational Attempt",
        "metric_locos_attempt": "LOCOS Attempt",
        "metric_referrals_today": "Member Referrals Today",
        "metric_nm_texts": "NM Texts Sent",
        "metric_pew": "Potential at Sacrament",
        "metric_date_metric": "Friends on Date",
        "metric_gate": "Baptized & Confirmed",
        "metric_renew": "Recent Converts at Church",
        "metric_rc_total": "RC Total",
        # --- Status labels ---
        "status_on_track": "On Track",
        "status_partial": "Partial",
        "status_behind": "Behind",
        "status_strong": "Strong",
        "status_developing": "Developing",
        "status_needs_attention": "Needs Attention",
        "status_high": "High",
        "status_medium": "Medium",
        "status_low": "Low",
        "status_pending": "Pending",
        "status_accepted": "Accepted",
        "status_rejected": "Rejected",
        "status_hold": "Hold",
        # --- Calendar labels ---
        "calendar_on_time": "On time",
        "calendar_late": "Late",
        "calendar_missed": "Missed",
        "calendar_upcoming": "Upcoming / pre-tracking",
        "calendar_before_tracking": "Before tracking started",
        "days_short": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        # --- Section headers ---
        "section_submission_status": "Submission Status — All-Time",
        "section_weekly_ki": "Weekly Key Indicators — Last 7 Days",
        "section_zone_summary": "Zone Summary — Last 7 Days",
        "section_8_week_trend": "8-Week Trend",
        "section_nightly_compliance": "Nightly Submission Compliance",
        "section_goals_vs_actuals": "Goals vs Actuals",
        "section_effort_by_area": "Effort by Area",
        "section_daily_activity": "Daily Activity — Last 30 Days",
        "section_anomaly_flags": "Anomaly Flags",
        "section_contact_performance": "Contact Performance",
        "section_area_rankings": "Area Rankings",
        "section_find_pipeline": "Find Pipeline",
        # --- Filter/control labels ---
        "filter_all_zones": "All Zones",
        "filter_zone": "Zone",
        "filter_district": "District",
        "filter_area": "Area",
        "filter_any": "— any —",
        "filter_select": "— select —",
        "filter_show": "Show",
        "filter_behind_only": "Behind only",
        "filter_on_track_only": "On Track only",
        "filter_time_range": "Time Range",
        "filter_last_7_days": "Last 7 Days",
        "filter_transfer_to_date": "Transfer to Date",
        "filter_all_time": "All Time",
        "filter_this_week_vs_last": "This Week vs Last Week",
        "filter_4_weeks": "Last 4 Weeks vs Prior 4 Weeks",
        "filter_view_by": "View by",
        "filter_mission_wide": "Mission-Wide",
        "filter_days_displayed": "Days displayed",
        "filter_sort_newest": "Newest",
        "filter_sort_oldest": "Oldest",
        # --- Button labels ---
        "btn_save_goals": "Save Goals",
        "btn_reset_defaults": "Reset to Mission Defaults",
        "btn_yes_reset": "Yes, reset",
        "btn_cancel": "Cancel",
        "btn_save_note": "Save Note",
        "btn_accept": "Accept",
        "btn_reject": "Reject",
        "btn_hold": "Hold",
        "btn_reopen": "Re-open",
        "btn_delete": "Delete",
        "btn_edit": "Edit",
        "btn_generate_mission_pdf": "Generate Mission PDF",
        "btn_generate_stake_report": "Generate Stake Report",
        "btn_clear_cache": "Clear Cache and Reload",
        "btn_run_scraper": "Run Scraper Now",
        # --- Info/warning/error messages ---
        "msg_no_data": "No data for this section yet.",
        "msg_no_areas_match": "No areas match the current filter.",
        "msg_companionship_not_found": "Companionship info not found in MISSION_ORG.",
        "msg_no_weekly_goals": "No weekly goals configured for this area.",
        "msg_no_anomalies": "No anomalies detected",
        "msg_note_required": "Note content is required.",
        "msg_note_saved": "Note saved.",
        # --- Tab labels ---
        "tab_mission_goals": "Mission Goals",
        "tab_area_goal_customization": "Area Goal Customization",
        "tab_lessons": "Lessons",
        "tab_finding": "Finding",
        "tab_contacts": "Contacts",
        "tab_lsi_attempts": "LSI & Attempts",
        "tab_effort": "Effort",
        "tab_mission_report": "Mission Report",
        "tab_stake_report": "Stake Report",
        "tab_effort_metrics": "Effort Metrics",
        "tab_skill_metrics": "Skill Metrics",
        "tab_ki_metrics": "Key Indicator Metrics",
        # --- Score labels ---
        "score_effort": "Effort",
        "score_skill": "Skill",
        "score_ki": "KI",
        "score_effectiveness": "Effectiveness",
        # --- Auth messages ---
        "auth_session_expired": "Your session has expired. Please sign in again.",
        "auth_access_denied": "Access denied. You must be signed in with an approved Google account. Contact the mission office if you need access.",
        "auth_identity_error": "Could not verify your identity. Please sign out and sign back in.",
    },
    "ES": {
        # --- Metric labels ---
        "metric_nm_lessons": "Lecciones con No Miembros",
        "metric_member_lessons": "Lecciones con Miembro Presente",
        "metric_rc_lessons": "Lecciones con Conversos Recientes",
        "metric_la_lessons": "Lecciones con Menos Activos",
        "metric_lsi_given": "ASI Dado (Ama/Sirve/Invita)",
        "metric_lsi_followups": "Seguimientos de ASI",
        "metric_new_found": "Personas Nuevas Encontradas",
        "metric_online_referrals": "Referencias en Línea",
        "metric_nm_doors": "Puertas a No Miembros",
        "metric_nm_contacted": "No Miembros Contactados",
        "metric_nm_meaningful": "Convs. Significativas con NM",
        "metric_mmm_sent": "MMMs Enviados",
        "metric_la_attempt": "Intentos con Menos Activos",
        "metric_fellowshipper_attempt": "Intentos con Compañero de Bienvenida",
        "metric_aux_attempt": "Intentos de Coordinación Aux.",
        "metric_info_attempt": "Intento Informativo",
        "metric_locos_attempt": "Intento LOCOS",
        "metric_referrals_today": "Referencias de Miembros Hoy",
        "metric_nm_texts": "Mensajes Enviados a NM",
        "metric_pew": "Personas en Reunión Sacramental",
        "metric_date_metric": "Amigos con Fecha Bautismal",
        "metric_gate": "Bautizados y Confirmados",
        "metric_renew": "Conversos Recientes en la Iglesia",
        "metric_rc_total": "Total de Conversos Recientes",
        # --- Status labels ---
        "status_on_track": "Al Día",
        "status_partial": "Parcial",
        "status_behind": "Atrasado",
        "status_strong": "Fuerte",
        "status_developing": "En Desarrollo",
        "status_needs_attention": "Necesita Atención",
        "status_high": "Alto",
        "status_medium": "Medio",
        "status_low": "Bajo",
        "status_pending": "Pendiente",
        "status_accepted": "Aceptado",
        "status_rejected": "Rechazado",
        "status_hold": "En Pausa",
        # --- Calendar labels ---
        "calendar_on_time": "A tiempo",
        "calendar_late": "Tarde",
        "calendar_missed": "No enviado",
        "calendar_upcoming": "Próximo / antes del seguimiento",
        "calendar_before_tracking": "Antes del inicio del seguimiento",
        "days_short": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
        # --- Section headers ---
        "section_submission_status": "Estado de Envíos — Total",
        "section_weekly_ki": "Indicadores Clave Semanales — Últimos 7 Días",
        "section_zone_summary": "Resumen por Zona — Últimos 7 Días",
        "section_8_week_trend": "Tendencia de 8 Semanas",
        "section_nightly_compliance": "Cumplimiento de Informe Nocturno",
        "section_goals_vs_actuals": "Metas vs. Resultados",
        "section_effort_by_area": "Esfuerzo por Área",
        "section_daily_activity": "Actividad Diaria — Últimos 30 Días",
        "section_anomaly_flags": "Señales de Alerta",
        "section_contact_performance": "Rendimiento de Contactos",
        "section_area_rankings": "Clasificación por Área",
        "section_find_pipeline": "Canal de Contactos",
        # --- Filter/control labels ---
        "filter_all_zones": "Todas las Zonas",
        "filter_zone": "Zona",
        "filter_district": "Distrito",
        "filter_area": "Área",
        "filter_any": "— cualquiera —",
        "filter_select": "— seleccionar —",
        "filter_show": "Mostrar",
        "filter_behind_only": "Solo atrasados",
        "filter_on_track_only": "Solo al día",
        "filter_time_range": "Rango de tiempo",
        "filter_last_7_days": "Últimos 7 días",
        "filter_transfer_to_date": "Desde el inicio del transfer",
        "filter_all_time": "Desde el inicio",
        "filter_this_week_vs_last": "Esta semana vs. semana pasada",
        "filter_4_weeks": "Últimas 4 semanas vs. 4 anteriores",
        "filter_view_by": "Ver por",
        "filter_mission_wide": "Toda la Misión",
        "filter_days_displayed": "Días mostrados",
        "filter_sort_newest": "Más recientes",
        "filter_sort_oldest": "Más antiguos",
        # --- Button labels ---
        "btn_save_goals": "Guardar Metas",
        "btn_reset_defaults": "Restablecer Metas de la Misión",
        "btn_yes_reset": "Sí, restablecer",
        "btn_cancel": "Cancelar",
        "btn_save_note": "Guardar Nota",
        "btn_accept": "Aceptar",
        "btn_reject": "Rechazar",
        "btn_hold": "Pausar",
        "btn_reopen": "Reabrir",
        "btn_delete": "Eliminar",
        "btn_edit": "Editar",
        "btn_generate_mission_pdf": "Generar PDF de la Misión",
        "btn_generate_stake_report": "Generar Informe del Estaca",
        "btn_clear_cache": "Limpiar Caché y Recargar",
        "btn_run_scraper": "Ejecutar Ahora",
        # --- Info/warning/error messages ---
        "msg_no_data": "Aún no hay datos para esta sección.",
        "msg_no_areas_match": "Ningún área coincide con el filtro actual.",
        "msg_companionship_not_found": "Información de la companía no encontrada en MISSION_ORG.",
        "msg_no_weekly_goals": "No hay metas semanales configuradas para esta área.",
        "msg_no_anomalies": "No se detectaron anomalías",
        "msg_note_required": "El contenido de la nota es obligatorio.",
        "msg_note_saved": "Nota guardada.",
        # --- Tab labels ---
        "tab_mission_goals": "Metas de la Misión",
        "tab_area_goal_customization": "Personalización de Metas por Área",
        "tab_lessons": "Lecciones",
        "tab_finding": "Contactos Nuevos",
        "tab_contacts": "Contactos",
        "tab_lsi_attempts": "ASI e Intentos",
        "tab_effort": "Esfuerzo",
        "tab_mission_report": "Informe de la Misión",
        "tab_stake_report": "Informe del Estaca",
        "tab_effort_metrics": "Métricas de Esfuerzo",
        "tab_skill_metrics": "Métricas de Habilidad",
        "tab_ki_metrics": "Indicadores Clave",
        # --- Score labels ---
        "score_effort": "Esfuerzo",
        "score_skill": "Habilidad",
        "score_ki": "IC",
        "score_effectiveness": "Efectividad",
        # --- Auth messages ---
        "auth_session_expired": "Tu sesión ha expirado. Por favor inicia sesión nuevamente.",
        "auth_access_denied": "Acceso denegado. Debes iniciar sesión con una cuenta de Google aprobada. Contacta a la oficina de la misión si necesitas acceso.",
        "auth_identity_error": "No se pudo verificar tu identidad. Por favor cierra sesión y vuelve a iniciar.",
    },
}


def t(key: str) -> str:
    """Get a translated string for the current mission language."""
    lang = get_mission_language()
    result = _STRINGS.get(lang, _STRINGS["EN"]).get(key)
    if result is None:
        result = _STRINGS["EN"].get(key, key)
    return result
```

### 2.4 — Replace hardcoded "Utah Provo Mission" in all Python files

Open each file below and make the specified change. In VS Code, use **Ctrl+H** (Find & Replace) with "Match Case" ON.

**Add this import at the top of each modified file:**
```python
from app.config.mission import get_mission_name
```

**Files to update and what to change:**

| File | Find | Replace |
|------|------|---------|
| `pages/01_dashboard.py` line 30 | `subtitle="Utah Provo Mission"` | `subtitle=get_mission_name()` |
| `pages/02_Goals.py` line 28 | `subtitle="Utah Provo Mission"` | `subtitle=get_mission_name()` |
| `pages/03_Mission_Breakdown.py` line 42 | `subtitle="Utah Provo Mission"` | `subtitle=get_mission_name()` |
| `pages/04_Zone_Breakdown.py` line 224 | `subtitle="Utah Provo Mission"` | `subtitle=get_mission_name()` |
| `pages/06_Scores.py` line 367 | `subtitle="Utah Provo Mission"` | `subtitle=get_mission_name()` |
| `pages/08_Daily_Activity.py` line 93 | `subtitle="Utah Provo Mission"` | `subtitle=get_mission_name()` |
| `pages/09_Analyze.py` line 68 | `subtitle="Utah Provo Mission"` | `subtitle=get_mission_name()` |
| `pages/10_Notes.py` line 77 | `subtitle="Utah Provo Mission"` | `subtitle=get_mission_name()` |
| `pages/11_Reports.py` line 49 | `subtitle="Utah Provo Mission"` | `subtitle=get_mission_name()` |
| `pages/12_Data_Status.py` line 21 | `subtitle="Utah Provo Mission"` | `subtitle=get_mission_name()` |
| `pages/14_Referrals.py` line 41 | `subtitle="Utah Provo Mission"` | `subtitle=get_mission_name()` |
| `pages/15_Suggestions.py` line 26 | `subtitle="Utah Provo Mission"` | `subtitle=get_mission_name()` |
| `Home.py` line 95 | `"Utah Provo Mission · Welcome back,` | `f"{get_mission_name()} · Welcome back,` |
| `app/main.py` line 67 | `"Utah Provo Mission Analytics Platform"` | `f"{get_mission_name()} Analytics Platform"` |
| `app/chat/gemini_chat.py` line 684 | `"…APs of the Utah Provo Mission…"` | (use `get_mission_name()` in the f-string — find "Utah Provo Mission" in the system prompt string and replace with `{get_mission_name()}`) |
| `app/export/pdf_builder.py` | All 5 occurrences of `"Utah Provo Mission"` | Replace each with `get_mission_name()` — use Ctrl+H in that file |
| `app/export/stake_report.py` | Both occurrences of `"Utah Provo Mission"` | Replace each with `get_mission_name()` |

**Also fix timezone in `app/utils/area_helpers.py`:**
1. Add import at top: `from app.config.mission import get_mission_timezone`
2. Find line 8: `_MOUNTAIN_TZ = "America/Denver"`
3. Change to: `_MOUNTAIN_TZ = get_mission_timezone()`

**Also fix ZONES_ORDERED in `app/export/pdf_builder.py`:**
Find the `ZONES_ORDERED = [...]` list and replace the entire thing with:
```python
def _get_zones_ordered(df_org) -> list:
    return sorted(df_org["Zone"].dropna().unique().tolist())
```
Then find where `ZONES_ORDERED` is used (it's passed as a sort key) and replace `ZONES_ORDERED` with `_get_zones_ordered(df_org)`. The `df_org` variable should already be available in context.

**Also fix Reports timezone in `pages/11_Reports.py` line 159:**
Find: `mt_tz = zoneinfo.ZoneInfo("America/Denver")`
Replace: `mt_tz = zoneinfo.ZoneInfo(get_mission_timezone())`
(Add `from app.config.mission import get_mission_timezone` at top)

### 2.5 — Update Helpers.gs in Apps Script

Open the Apps Script editor for the **Utah Provo Mission** project:
1. Open `COMPASS_Main` Google Sheet
2. Click **Extensions → Apps Script**
3. Open `Helpers.gs`

At the very top of `Helpers.gs`, find the section with variable declarations (around line 220–230 where `SENDER_NAME` is defined). Add these lines right above or below `SENDER_NAME`:

```javascript
// Mission identity — read from AGENT_CONFIG so this file works for any mission
var MISSION_NAME = getConfig('MISSION_NAME') || 'PMG Compass';
var MISSION_LANGUAGE = (getConfig('MISSION_LANGUAGE') || 'EN').toUpperCase();
var MISSION_TIMEZONE = getConfig('MISSION_TIMEZONE') || 'America/Denver';
```

Then find line 225: `var SENDER_NAME = 'PMG Compass — Utah Provo Mission';`
Change to: `var SENDER_NAME = 'PMG Compass — ' + MISSION_NAME;`

Now do a **global Find & Replace** in the Apps Script editor (Ctrl+H):
- Find: `Utah Provo Mission`
- Replace: `' + MISSION_NAME + '`

⚠️ After replacing, carefully check each occurrence. Some are inside string literals and need the quotes joined properly. For example:
- `'PMG Compass | Utah Provo Mission'` → `'PMG Compass | ' + MISSION_NAME`
- `"Utah Provo Mission"` (standalone) → `MISSION_NAME`
- `"the Utah Provo Mission"` → `"the " + MISSION_NAME`

Go through each of these .gs files and verify the replacement looks correct:
- `Helpers.gs` — SENDER_NAME line
- `Agent1C.gs` — subject line, unitName, Gemini prompts
- `Agent2.gs` — email subject/footer
- `Agent3.gs` — email footers and escalation text
- `Agent4.gs` — health report footer
- `Agent6.gs` — email subject + footer
- `Agent7.gs` — email footer
- `AgentQA.gs` — Gemini system prompt
- `AgentReminder.gs` — email footers
- `AgentReferral.gs` — email bodies
- `RelayReferrals.gs` — sender name

Also fix timezone references in `AgentEscalation.gs`:
- Find all: `'America/Denver'`
- Replace with: `MISSION_TIMEZONE`
(Make sure `MISSION_TIMEZONE` is accessible — either import via getConfig or move Helpers.gs vars into a shared function)

### 2.6 — Test the multi-mission config

1. In `COMPASS_Main` → `AGENT_CONFIG`, temporarily change `MISSION_NAME` to `"TEST MISSION 123"`
2. Open the Streamlit app (local or Cloud)
3. Navigate to any page — the header subtitle should show "TEST MISSION 123"
4. Check the PDF builder — run a test PDF, the header should show "TEST MISSION 123"
5. Change it back to `"Utah Provo Mission"` when done

### 2.7 — Commit the changes

```bash
cd "C:\Users\2011794-MTS\Desktop\PMG-Compass"
git add app/config/mission.py app/utils/strings.py app/utils/area_helpers.py app/export/pdf_builder.py app/export/stake_report.py app/chat/gemini_chat.py app/main.py app/auth/auth.py Home.py pages/
git commit -m "Add multi-mission config: mission name/language/timezone driven from AGENT_CONFIG"
git push
```

---

## STEP 3 — Wire Spanish Translations into the App Pages
### ⚠️ ONE-TIME — adds i18n to the app; future missions just update AGENT_CONFIG

Now that `strings.py` exists (Step 2.3) with full English and Spanish translations, you need to update each page file to USE those translations instead of hardcoded strings.

### 3.1 — Update metric label dicts in pages

The metric labels `"NM Lessons"`, `"New Found"`, etc. are duplicated in at least 5 files. Replace each dict with calls to `t()`.

**`pages/04_Zone_Breakdown.py`** — Find `METRIC_OPTIONS = {...}` and replace:
```python
from app.utils.strings import t
METRIC_OPTIONS = {
    "nm_lessons": t("metric_nm_lessons"),
    "member_lessons": t("metric_member_lessons"),
    # ... replace each key similarly
}
```
Do the same for each METRIC_OPTIONS/METRIC_LABELS dict in: `pages/06_Scores.py`, `pages/08_Daily_Activity.py`, `pages/09_Analyze.py`, `app/utils/area_helpers.py` (the `format_metric_label()` function).

### 3.2 — Update calendar day labels

**`pages/03_Mission_Breakdown.py`** and **`pages/05_Area_Breakdown.py`**:
Find: `["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]`
Replace with: `t("days_short")`
(Add `from app.utils.strings import t` at top of each file)

### 3.3 — Update calendar legend labels
Find strings like `"On time"`, `"Late"`, `"Missed"` in the calendar color-coding sections.
Replace with `t("calendar_on_time")`, `t("calendar_late")`, `t("calendar_missed")`, etc.

### 3.4 — Update status strings
Find all instances of `"On Track"`, `"Behind"`, `"Partial"`, `"Strong"`, `"Developing"`, `"Needs Attention"` across all page files.
Replace with `t("status_on_track")` etc.

**Pro tip:** In VS Code, open the search panel (Ctrl+Shift+F), search for `"On Track"` with quotes — it will show every file. Click through each one and replace.

### 3.5 — Update auth messages in `app/auth/auth.py`
Find the hardcoded English error strings and replace with `t("auth_session_expired")` etc.
Add `from app.utils.strings import t` at the top.

### 3.6 — Commit after all page files updated

```bash
git add pages/ app/auth/ app/utils/strings.py
git commit -m "Wire i18n strings.py into all page files — Spanish/English switchable via AGENT_CONFIG"
git push
```

---

## STEP 4 — Translate Email Templates in Apps Script
### ⚠️ ONE-TIME — future missions just set MISSION_LANGUAGE in their AGENT_CONFIG

### 4.1 — Update Agent3.gs (missed-days alerts to missionaries)

In Apps Script, open `Agent3.gs`.

The `a3_sendMissedDaysEmail()` function currently builds English HTML. Wrap the content in a language check:

```javascript
function a3_buildMissedDaysHTML(areaName, missedList) {
  if (MISSION_LANGUAGE === 'ES') {
    return a3_buildMissedDaysHTML_ES(areaName, missedList);
  }
  return a3_buildMissedDaysHTML_EN(areaName, missedList);
}
```

Move the existing English HTML into `a3_buildMissedDaysHTML_EN()`, then create `a3_buildMissedDaysHTML_ES()`:

```javascript
function a3_buildMissedDaysHTML_ES(areaName, missedList) {
  var missedItems = missedList.map(function(d) {
    return '<li>' + d + '</li>';
  }).join('');
  return '<div style="font-family: Arial, sans-serif; max-width: 600px;">' +
    '<h2 style="color: #173A72;">Alerta: Informes Nocturnos Faltantes</h2>' +
    '<p>Hola,</p>' +
    '<p>El área <strong>' + areaName + '</strong> no ha enviado su informe nocturno en las siguientes fechas:</p>' +
    '<ul>' + missedItems + '</ul>' +
    '<p>Por favor contacta a esta companía para ayudarles a ponerse al día.</p>' +
    '<p><a href="' + getConfig('NIGHTLY_FORM_LINK') + '" style="background:#173A72;color:white;padding:10px 20px;text-decoration:none;border-radius:4px;">Enviar Informe Nocturno</a></p>' +
    '<p style="color:#999;font-size:12px;">PMG Compass — ' + MISSION_NAME + '</p>' +
    '</div>';
}
```

Do the same for District Leader escalation emails and companionship reminder emails.

### 4.2 — Update AgentQA.gs

In the Gemini system prompt, add the language instruction:

Find the system prompt string (around line 384). Add this at the top:
```javascript
var systemPrompt = 'Respond in ' + (MISSION_LANGUAGE === 'ES' ? 'Spanish' : 'English') + '. ';
systemPrompt += 'You are PMG Compass, an AI assistant for ' + MISSION_NAME + '. ';
// ... rest of existing prompt
```

### 4.3 — Update Agent1C.gs (coaching emails)

Find the Gemini narrative generation prompts (the ones that say "Write a brief coaching narrative for..."). Add to each prompt:
```javascript
prompt += '\n\nIMPORTANT: Write your response in ' + (MISSION_LANGUAGE === 'ES' ? 'Spanish' : 'English') + '.';
```

For the HTML email template functions in Agent1C, wrap subject lines and structural text in language checks:
```javascript
var emailSubject = MISSION_LANGUAGE === 'ES'
  ? 'PMG Compass — Entrenamiento Semanal | ' + weekLabel
  : 'PMG Compass — Weekly Coaching | ' + weekLabel;
```

Key Spanish translations for Agent1C structural text:
- `"Week ending {date}"` → `"Semana que termina el {date}"`
- `"💪 Strength — {metric}"` → `"💪 Fortaleza — {metric}"`
- `"📈 Growth Focus — {metric}"` → `"📈 Área de Crecimiento — {metric}"`
- `"Mission Summary"` → `"Resumen de la Misión"`
- `"Zone Summary — {zone}"` → `"Resumen de Zona — {zone}"`
- `"District Summary — {district}"` → `"Resumen de Distrito — {district}"`
- `"View PMG Compass Dashboard"` → `"Ver Panel de PMG Compass"`

### 4.4 — Update AgentReminder.gs

In the weekly compliance reminder email body, wrap in a language check like the Agent3 pattern above. Spanish for the key phrase:
- Subject: `"Recordatorio: Envío de Informe Semanal — {mission}"`
- Body: `"¡Hola! Este es tu recordatorio para enviar el informe nocturno de esta semana..."`
- Submit button: `"Enviar Informe Ahora"`

---

## STEP 5 — Translate the MESSAGE_BANK (Coaching Messages)
### ⚠️ ONE-TIME for infrastructure; content translation is mission-specific

### 5.1 — Add Language column to MESSAGE_BANK tab

1. Open `COMPASS_Main` Google Sheet
2. Click the `MESSAGE_BANK` tab
3. Find the header row (Row 1)
4. Click on the column header after `Active` — insert a new column
5. Type `Language` as the header
6. For all existing rows, fill in `EN` in the Language column
   - Quick way: type `EN` in the first data row, then select that cell, Ctrl+Shift+End to select down to the last row, Ctrl+D to fill down

### 5.2 — Update Agent1B to filter by language

In Apps Script, open `Agent1B.gs`. Find the `a1b_loadMessageBank()` function.

Find where it filters messages (probably by `Active === 'TRUE'`). Add the language filter:
```javascript
var lang = MISSION_LANGUAGE || 'EN';
messages = messages.filter(function(row) {
  var active = row[activeCol] === 'TRUE' || row[activeCol] === true;
  var msgLang = (row[languageCol] || 'EN').toString().toUpperCase();
  return active && msgLang === lang;
});
```

You'll need to find `languageCol` — it's the column index of the new Language column you just added.

### 5.3 — Add Spanish coaching messages

Now comes content work. The MESSAGE_BANK has ~60 active coaching messages (3 per metric, 20 metrics). You need Spanish versions.

**Method (fastest approach — use Gemini to draft, you review):**

1. Export the MESSAGE_BANK tab as CSV (File → Download → CSV)
2. Open a new chat with Gemini (gemini.google.com)
3. Paste the CSV content and say: `"Translate the Subject_Line and Body_Text columns to Spanish for LDS missionaries in Chile. Keep the same tone — warm, encouraging, mission-focused. Keep the scripture references but translate them to use Spanish LDS book names (e.g., '1 Nephi', 'Moroni', 'Mateo', 'Mosíah'). Return the result as a CSV with the same column headers plus a Language column set to 'ES' for each row."`
4. Review the output carefully — check that:
   - Names of God/Christ are correct: "Dios", "Jesucristo", "El Salvador"
   - PMG chapter references work: "Predica Mi Evangelio, Capítulo X"
   - The tone matches the English (warm, not stiff)
5. Once reviewed, paste the Spanish rows back into MESSAGE_BANK (add them as new rows below the English rows)
6. Set `Language = ES` for each new row

### 5.4 — Add Spanish KNOWLEDGE_BASE entries (for AgentQA)

Same process as 5.3. Export KNOWLEDGE_BASE, translate with Gemini, review, re-import with `Language = ES`.

Agent3's `a3_loadKnowledgeBase()` function needs the same language filter treatment (Step 5.2 approach).

---

## STEP 6 — Set Up the CCSM Google Sheet
### 🔁 REUSABLE — do this for every new mission

### 6.1 — Duplicate COMPASS_Main

1. Open `COMPASS_Main` Google Sheet
2. Click **File → Make a copy**
3. Name it: `COMPASS_CCSM`
4. Location: put it in the same Google Drive folder as COMPASS_Main
5. Click **OK** — this creates an exact copy with all tabs and data

### 6.2 — Clear data tabs in COMPASS_CCSM

⚠️ Don't delete the tabs — just clear the data while keeping the header row.

For each of these tabs, click the tab, select all data rows (click Row 2, Ctrl+Shift+End, Delete):
- `NIGHTLY_FORM_RAW` — delete all rows except header
- `WEEKLY_FORM_RAW` — delete all rows except header
- `DAILY_LOG` — delete all rows except header
- `LIVE_SNAPSHOT` — delete all rows except header
- `WEEKLY_KI` — delete all rows except header
- `MISSING_LOG` — delete all rows except header
- `AGENT_LOG` — delete all rows except header
- `SUGGESTIONS` — delete all rows except header
- `SUGGESTIONS_REVIEW` — delete all rows except header
- `NOTES` — delete all rows except header
- `GOALS_CONFIG` — delete all rows except header (you'll add CCSM goals later)

**Keep these tabs as-is (they have structural/config data):**
- `QUESTIONS_CONFIG` (will update in Step 6.3)
- `AGENT_CONFIG` (will update in Step 6.4)
- `MESSAGE_BANK` (already has EN + ES rows from Step 5)
- `KNOWLEDGE_BASE` (already has EN + ES rows from Step 5.4)
- `TABLEAU_RANKING` (clear if it has Provo-specific data)

### 6.3 — Update QUESTIONS_CONFIG for CCSM

The QUESTIONS_CONFIG tab defines which metrics to track. CCSM chose their stats via the intake form (Step 1). Update this tab to match.

1. Click the `QUESTIONS_CONFIG` tab in COMPASS_CCSM
2. Delete all data rows (keep header)
3. Add rows for each stat CCSM chose in the intake form

For each NIGHTLY stat CCSM selected, create one row:
| Question_ID | Form_Type | Form_Column_Header | Metric_Key | Metric_Display_Name | Data_Type | Include_In_Daily_Log | Include_In_Live_Snapshot | Include_In_Weekly_Breakdown | Display_Order | Active |
|---|---|---|---|---|---|---|---|---|---|---|
| Q-N-001 | NIGHTLY | (Spanish question text) | nm_lessons | Lecciones con NM | NUMBER | TRUE | TRUE | TRUE | 1 | TRUE |

**Column header values for CCSM (Spanish):**

The "Form_Column_Header" is the EXACT text of the question as it will appear in the Google Form. Use these Spanish translations for the standard stats:

| Metric_Key | Spanish Form Question |
|---|---|
| nm_lessons | Lecciones con No Miembros |
| member_lessons | Lecciones con Miembro Presente |
| rc_lessons | Lecciones con Conversos Recientes |
| la_lessons | Lecciones con Menos Activos |
| lsi_given | Miembros a los que se les dio ASI (Ama/Sirve/Invita) |
| lsi_followups | Seguimientos de ASI realizados |
| new_found | Personas Nuevas Encontradas |
| online_referrals | Referencias en Línea Recibidas |
| nm_doors | Intento de Contacto con No Miembros |
| nm_contacted | No Miembros Contactados |
| nm_meaningful | Conversaciones Significativas con No Miembros |
| mmm_sent | ¿Cuántos MMM enviaste hoy? |
| la_Attempt | Intento con Menos Activos |
| fellowshipper_Attempt | Intento con Compañero de Bienvenida |
| aux_Attempt | Intento de Coordinación Auxiliar |
| info_Attempt | Intento Informativo |
| locos_Attempt | Intento LOCOS |
| referrals_today | Referencias de Miembros de Hoy |
| nm_texts | ¿Cuántos mensajes enviaste a No Miembros hoy? |

For WEEKLY stats (Pew/Date/Gate/Renew/Total), add rows with Form_Type = WEEKLY:
| Metric_Key | Spanish Form Question |
|---|---|
| pew | Personas No Miembros en Reunión Sacramental (Banco) |
| date_metric | Amigos con Fecha Bautismal (Fecha) |
| gate | Bautizados y Confirmados (Puerta) |
| renew | Conversos Recientes en la Iglesia Esta Semana (Renovar) |
| rc_total | Conversos Recientes que Pudieron Haber Asistido (Total) |

### 6.4 — Update AGENT_CONFIG in COMPASS_CCSM

Click the `AGENT_CONFIG` tab. Update these key values:

| Key | New Value |
|---|---|
| `MISSION_NAME` | `Chile Concepción South Mission` |
| `MISSION_LANGUAGE` | `ES` |
| `MISSION_TIMEZONE` | `America/Santiago` |
| `MISSION_LOCALE` | `es_CL` |
| `NIGHTLY_FORM_LINK` | (leave blank for now — fill in Step 8) |
| `SYSTEM_START_DATE` | (CCSM's start date from intake form) |
| `TRANSFER_START_DATE` | (CCSM's first transfer date) |
| `MISSED_DAYS_LOOKBACK` | `3` (same default) |

Leave RELAY_1_URL and RELAY_2_URL as-is for now.

### 6.5 — Update MISSION_ORG in COMPASS_CCSM

Click the `MISSION_ORG` tab. Delete all existing data rows (keep header).

Now populate it with CCSM's missionary roster from the intake form.

Header row should be:
```
Area_ID | Area_Name | Zone | District | Language_Type | Companion1_Name | Companion1_Email | Companion2_Name | Companion2_Email | Is_DL | Is_ZL | Is_STL | Is_AP | Is_MP | Active
```

Add one row per companionship. Rules:
- `Area_ID`: sequential numbers starting at 1
- `Language_Type`: `ES` for CCSM (Spanish-speaking areas)
- `Is_DL/ZL/STL/AP/MP`: `TRUE` or `FALSE`
- `Active`: `TRUE` for all current missionaries
- Emails MUST be Church-issued `@missionary.org` emails for missionaries

Also add the Mission President and APs as special rows:
- MP row: `Is_MP = TRUE`, leave Companion2 blank
- AP rows: `Is_AP = TRUE`

---

## STEP 7 — Create CCSM Google Forms (Daily and Weekly)
### 🔁 REUSABLE — create fresh forms for each mission

### 7.1 — Create the CCSM Nightly Form

Go to [forms.google.com](https://forms.google.com) while logged in as `pmg.compass@gmail.com`.

1. Create a new blank form
2. Title: `PMG Compass — Informe Nocturno | Chile Concepción South Mission`
3. Description:
   ```
   Por favor llena este formulario cada noche con los datos del día.
   Llena una sección por cada zona.
   ```

The form structure mirrors the Utah form but with Spanish questions and CCSM zones/areas.

**Form architecture:** The form uses a "section per zone" structure. Each zone section has:
- `¿Cuál es tu área?` (dropdown of area names in that zone)
- `¿Qué fecha estás registrando?` (date)
- One number question per metric (from QUESTIONS_CONFIG, same Spanish text)
- `¿Cuánto esfuerzo pusiste hoy?` (multiple choice: Todo / La Mayoría / Algo)

To build it:
1. Add a Section for each CCSM zone (name it the zone name)
2. Within each section, add the area dropdown — **the options MUST exactly match the Area_Name values in MISSION_ORG**
3. Add the date question
4. Add one question per stat (use Spanish text from QUESTIONS_CONFIG)
5. Add the effort question

**Connect to COMPASS_CCSM sheet:**
- Click the three-dot menu (⋮) in the Responses tab → **Select response destination**
- Choose "Select existing spreadsheet" → navigate to `COMPASS_CCSM`
- Choose the `NIGHTLY_FORM_RAW` tab as the destination

### 7.2 — Create the CCSM Weekly Form

Same process as 7.1 but shorter. Title: `PMG Compass — Informe Semanal | Chile Concepción South Mission`

Structure:
- `¿Cuál es tu Zona?` (dropdown of zone names)
- One section per zone, each with:
  - `¿Cuál es tu Área?` (dropdown)
  - `¿Para qué semana estás registrando? (fecha del domingo que termina la semana)`
  - One question per KI metric (from QUESTIONS_CONFIG WEEKLY rows)

Connect responses to `COMPASS_CCSM → WEEKLY_FORM_RAW`.

### 7.3 — Update AGENT_CONFIG with form links

After creating both forms:
1. Open each form
2. Click **Send → link icon (🔗) → copy link**
3. Open `COMPASS_CCSM → AGENT_CONFIG`
4. Update: `NIGHTLY_FORM_LINK` → paste the nightly form link
5. Update: `WEEKLY_FORM_LINK` → paste the weekly form link (if Agent1A uses it)

---

## STEP 8 — Set Up CCSM Apps Script Project
### 🔁 REUSABLE — create a new bound project for each mission

### 8.1 — Create the Apps Script project

1. Open `COMPASS_CCSM` Google Sheet
2. Click **Extensions → Apps Script**
3. This creates a new Apps Script project **bound to COMPASS_CCSM**
4. Name the project: `PMG Compass — Chile Concepción South Mission`

### 8.2 — Paste all .gs files

In the Apps Script editor:

For each .gs file in `C:\Users\2011794-MTS\Desktop\PMG-Compass\docs\`:
1. Click **"+"** (New file) in the Apps Script sidebar
2. Name it the same as the .gs filename (without the .gs extension)
3. Open the corresponding file from the repo
4. Select all content (Ctrl+A), copy, paste into the Apps Script editor
5. Click Save (Ctrl+S)

Files to paste (in order — Helpers.gs FIRST since others depend on it):
- `Helpers.gs`
- `Agent1A.gs`
- `Agent1B.gs`
- `Agent1C.gs`
- `Agent2.gs`
- `Agent3.gs`
- `Agent4.gs`
- `Agent5A.gs`
- `Agent5B.gs` (if active)
- `Agent6.gs`
- `Agent7.gs`
- `AgentDuplicate.gs`
- `AgentQA.gs`
- `AgentReminder.gs`

Do NOT paste referral system files unless CCSM uses the referral system.

### 8.3 — Set the project timezone

1. In Apps Script editor, click **Project Settings** (gear icon in sidebar)
2. Find **Time zone** → change from UTC/Denver to `(GMT-04:00) Santiago` (Chile Standard Time)
   - Note: Chile uses `America/Santiago` which adjusts for daylight saving time automatically

### 8.4 — Run setup functions

In the Apps Script editor, run these functions one at a time (click the function name in the dropdown at top, then click ▶ Run):

1. **`setupQuestionsConfig()`** (in Agent3.gs) — this seeds QUESTIONS_CONFIG in the sheet from the hardcoded rows. BUT since you already manually populated QUESTIONS_CONFIG in Step 6.3 with CCSM's stats, you may need to modify this function first to match CCSM's metrics, OR skip this function since the tab is already correct.

2. **`setupAgent7Trigger()`** (in Agent7.gs) — sets up the nightly Sister Ellis report trigger

3. **`setupAgent3Triggers()`** (in Agent3.gs) — sets up the 6 AM and 9 PM missed-days triggers. **Adjust the times to match Santiago timezone** — if you want 9 PM Santiago time, calculate what UTC hour that is (Santiago UTC-4 in summer = 1 AM UTC).

4. **`setupAgent1Triggers()`** (in Agent1A.gs) — sets up the Sunday coaching email triggers

5. **`setupAgentReminderTrigger()`** (in AgentReminder.gs) — sets up the weekly reminder

After running each setup function, go to **Triggers** (alarm clock icon in sidebar) and verify all triggers are created with the correct time.

### 8.5 — Test key agent functions

Run these test functions to verify the CCSM setup is working:

1. **`previewMissedDays()`** (Agent3.gs) — should show a preview of missed-days logic. Should use CCSM areas.
2. **`a2_dailySnapshot()`** (Agent2.gs) — dry run of the daily snapshot. Check AGENT_LOG tab after running to see if it found DAILY_LOG data.
3. Send one test submission to the CCSM Nightly Form (fill it out yourself) → then run **`a3_processNightlyForms()`** → check DAILY_LOG for the test row.

---

## STEP 9 — Deploy CCSM Streamlit Instance
### 🔁 REUSABLE — new Streamlit Cloud deployment per mission

### 9.1 — Get the COMPASS_CCSM sheet ID

1. Open `COMPASS_CCSM`
2. Look at the URL — it will be something like:
   `https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUv/edit#gid=0`
3. The sheet ID is the long string between `/d/` and `/edit` → e.g., `1AbCdEfGhIjKlMnOpQrStUv`
4. Copy this ID

### 9.2 — Create a new Streamlit Cloud deployment

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Log in as the account that owns the current deployment
3. Click **"New app"**
4. Fill in:
   - Repository: `your-github-username/PMG-Compass` (same repo as current app)
   - Branch: `main`
   - Main file path: `Home.py`
5. Click **Advanced settings**
6. In the **Secrets** section, paste this (replace values with CCSM specifics):

```toml
COMPASS_SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUv"  # CCSM sheet ID from Step 9.1
COMPASS_SHEET_NAME = "COMPASS_CCSM"

# Copy these from the existing app's secrets.toml — they're the same:
GOOGLE_SERVICE_ACCOUNT_JSON = '''
{your existing service account JSON here}
'''
SUPABASE_URL = "..."
SUPABASE_KEY = "..."
STREAMLIT_DEV_EMAIL = "pmg.compass@gmail.com"
```

7. Click **Deploy**
8. Wait ~2 minutes for the deployment to build
9. Streamlit will give you a URL like `https://pmg-compass-ccsm.streamlit.app` — this is the CCSM dashboard URL

### 9.3 — Share access with CCSM leadership

1. The app uses Google SSO — only approved email addresses can log in
2. Open `COMPASS_CCSM` → find the auth tab or wherever approved emails are stored
   (Check `AGENT_CONFIG` for `APPROVED_EMAILS` key, or check `app/auth/auth.py` for how emails are validated)
3. Add CCSM Mission President + APs' Church Gmail addresses to the approved list

---

## STEP 10 — Testing Checklist
### Run through this before going live

- [ ] **Config test:** Change `MISSION_NAME` to a test value in CCSM's AGENT_CONFIG → refresh dashboard → confirm name appears in header
- [ ] **Language test:** Confirm dashboard labels appear in Spanish (metric names, status badges, calendar day names)
- [ ] **Nightly form test:** Submit a test nightly form → verify row appears in `NIGHTLY_FORM_RAW` → run `a3_processNightlyForms()` → verify row appears in `DAILY_LOG` → refresh dashboard → verify data shows on the Dashboard page
- [ ] **Weekly form test:** Submit a test weekly form → verify row in `WEEKLY_FORM_RAW` → run `a5a_processWeeklyForms()` → check `WEEKLY_KI` tab
- [ ] **Missed-days alert test:** Manually insert a date 3 days ago with no form submission → run `previewMissedDays()` → confirm the area appears in the preview
- [ ] **Coaching email test:** Run `a1a_collectWeeklyData()` → run `a1b_buildMessages()` → run `a1c_sendEmails()` with test mode → verify a test coaching email arrives in Spanish
- [ ] **PDF test:** On the Reports page, click "Generar PDF de la Misión" → verify PDF downloads with CCSM name and Spanish headers
- [ ] **AgentQA test:** Submit a test question to the Q&A form → verify a Spanish response is generated

---

## STEP 11 — Future Mission Onboarding (The 1-Day Process)
### 🔁 This is the payoff — once everything above is done, new missions take ~1 day

When mission #3 (or #4, #5...) comes along, here is the complete checklist:

**Day 1 Morning (~2 hours):**
- [ ] Send them the intake form (Step 1 link — already exists, no rebuilding)
- [ ] While they fill it out, duplicate the Google Sheet (Step 6.1 — 5 minutes)
- [ ] Clear data tabs in the new sheet (Step 6.2 — 10 minutes)

**Day 1 Afternoon (~3 hours):**
- [ ] Review their intake form response
- [ ] Update AGENT_CONFIG with their mission name/language/timezone/start date (Step 6.4 — 15 minutes)
- [ ] Populate MISSION_ORG from their roster (Step 6.5 — 1 hour, depends on roster size)
- [ ] Update QUESTIONS_CONFIG from their selected stats (Step 6.3 — 30 minutes)
- [ ] Create their daily + weekly Google Forms (Step 7 — 1 hour)

**Day 2 Morning (~2 hours):**
- [ ] Create Apps Script project, paste files, set timezone, run setup functions (Step 8 — 1 hour)
- [ ] Deploy Streamlit instance (Step 9 — 30 minutes)
- [ ] Run testing checklist (Step 10 — 30 minutes)

**Total: ~7 hours for a new mission after the one-time code changes are done.**

The first time (CCSM) takes longer because of the one-time code changes in Steps 2–5. After that, those steps are done and every subsequent mission just runs Steps 1, 6, 7, 8, 9, and 10.

---

## Quick Reference: CCSM-Specific Values

| Item | Value |
|------|-------|
| Mission Name | Chile Concepción South Mission |
| Language (dashboard) | ES (Spanish) |
| Language (missionaries) | ES (Spanish) |
| Timezone | America/Santiago |
| Sheet Name | COMPASS_CCSM |
| Streamlit App URL | TBD after deployment |
| AgentQA email | pmg.compass@gmail.com (same relay) |
| Contact for setup | (from intake form) |

---

## Troubleshooting

**Problem:** Dashboard still shows "Utah Provo Mission" after updating AGENT_CONFIG  
**Fix:** Streamlit caches `get_mission_name()` for 1 hour. Click "Clear Cache and Reload" on the Data Status page, or wait 1 hour.

**Problem:** Apps Script functions show "Utah Provo Mission" in emails  
**Fix:** Make sure you ran Step 2.5 and saved the updated Helpers.gs. In Apps Script, `MISSION_NAME` is set at load time — re-saving the file clears the cached variable.

**Problem:** Nightly form responses not appearing in DAILY_LOG  
**Fix:** Check that the form response destination (Step 7.1) is set to the CCSM sheet's NIGHTLY_FORM_RAW tab, not the original Provo sheet.

**Problem:** Spanish strings showing key names like `metric_nm_lessons` instead of translated text  
**Fix:** Make sure `get_mission_language()` is returning `"ES"` — check AGENT_CONFIG `MISSION_LANGUAGE` value. Also verify strings.py has the ES dict populated.

**Problem:** PDF not showing CCSM zones in the right order  
**Fix:** After Step 2.4 (replacing ZONES_ORDERED), the PDF now sorts zones alphabetically from MISSION_ORG. If CCSM wants a specific order, add a `Zone_Order` column to MISSION_ORG and sort by it.

**Problem:** AgentQA still responding in English  
**Fix:** Verify `MISSION_LANGUAGE = ES` in CCSM AGENT_CONFIG. The Gemini prompt picks this up via `MISSION_LANGUAGE` variable in Helpers.gs — make sure Helpers.gs was re-pasted in the CCSM Apps Script project.
