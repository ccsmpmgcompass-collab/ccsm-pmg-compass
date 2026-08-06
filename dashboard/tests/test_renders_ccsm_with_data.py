"""Pages must render CCSM's vocabulary when they have DATA to render.

tests/test_renders_ccsm_metrics.py already asserts that no Provo key reaches
the screen — but it supplies only QUESTIONS_CONFIG and MISSION_ORG. Every
section that draws metrics returns early on empty data ("No daily activity data
yet", "No data for this section yet"), so the strings it was checking for never
had a chance to appear either way. That is the same blind spot the whole CCSM
de-contamination effort keeps hitting: mock the data to empty and there is
nothing left to be wrong about.

These tests supply a realistic DAILY_LOG, WEEKLY_KI, DASHBOARD_SUMMARY and
SCORE_CONFIG, so the Dashboard's KPI rows and the Scores page's Daily Activity
tab actually render, and then assert against the text those sections produce.

Fixtures mirror the live COMPASS_CCSM schema (probe of 2026-08-01): DAILY_LOG's
metric columns are QUESTIONS_CONFIG's nightly Metric_Keys, WEEKLY_KI's are the
seven ki_*_real / ki_*_meta pairs, and SCORE_CONFIG's two sections are separated
by a blank row.
"""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app.config import metric_catalog as mc

# ── Fixtures: a faithful slice of the live sheet ──────────────────────────────

_NIGHTLY = [
    ("report_date", "Fecha del Informe", "DATE"),
    ("exchanges", "Intercambios", "YESNO"),
    ("roleplays", "Prácticas de Enseñanza", "NUMBER"),
    ("contacts_attempted", "Intentos de Contacto", "NUMBER"),
    ("contacts_made", "Contactos", "NUMBER"),
    ("meaningful_conversations", "Conversaciones Significativas", "NUMBER"),
    ("new_people_found", "Nuevas Personas Encontradas", "NUMBER"),
    ("member_contacts", "Contactos con Miembros", "NUMBER"),
    ("bom_shared", "Libros de Mormón Entregados", "NUMBER"),
    ("effort", "Nivel de Esfuerzo", "CHOICE"),
]

_KI_BASES = [
    ("ki_new_people", "Nuevas Personas Encontradas"),
    ("ki_member_lessons", "Lecciones con Miembros"),
    ("ki_friends_sacrament", "Amigos en la Reunión Sacramental"),
    ("ki_friends_first_week", "Amigos en la Iglesia (Primera Semana)"),
    ("ki_baptismal_date", "Amigos con Fecha Bautismal"),
    ("ki_baptized_confirmed", "Bautizados y Confirmados"),
    ("ki_rc_at_church", "Conversos Recientes en la Iglesia"),
]


def _questions_config() -> pd.DataFrame:
    rows = [
        {"Question_ID": f"Q-N-{i:03d}", "Form_Type": "NIGHTLY",
         "Form_Column_Header": label, "Metric_Key": key,
         "Metric_Display_Name": label, "Data_Type": dtype,
         "Display_Order": i, "Active": "TRUE"}
        for i, (key, label, dtype) in enumerate(_NIGHTLY, start=1)
    ]
    rows.append({"Question_ID": "Q-W-001", "Form_Type": "WEEKLY",
                 "Form_Column_Header": "¿Qué fecha está ingresando?",
                 "Metric_Key": "report_date",
                 "Metric_Display_Name": "Fecha del Informe Semanal",
                 "Data_Type": "DATE", "Display_Order": 1, "Active": "TRUE"})
    n = 2
    for base, label in _KI_BASES:
        for suffix, word in (("_real", "Real"), ("_meta", "Meta")):
            rows.append({
                "Question_ID": f"Q-W-{n:03d}", "Form_Type": "WEEKLY",
                "Form_Column_Header": f"{label} ({word})",
                "Metric_Key": base + suffix,
                "Metric_Display_Name": f"{label} ({word})",
                "Data_Type": "NUMBER", "Display_Order": n, "Active": "TRUE"})
            n += 1
    return pd.DataFrame(rows)


#: SCORE_CONFIG as read_tab returns it — section 1, a blank separator row, then
#: section 2's own header and row. Weights are the live mission's.
SCORE_CONFIG = pd.DataFrame(
    [
        ["ALL", "contacts_attempted", "effort", "0.3", "TRUE"],
        ["ALL", "roleplays", "effort", "0.2", "TRUE"],
        ["ALL", "member_contacts", "effort", "0.2", "TRUE"],
        ["ALL", "effort", "effort", "0.3", "TRUE"],
        ["ALL", "contact_rate", "skill", "0.3", "TRUE"],
        ["ALL", "mc_rate", "skill", "0.25", "TRUE"],
        ["ALL", "lesson_rate", "skill", "0.25", "TRUE"],
        ["ALL", "close_rate", "skill", "0.2", "TRUE"],
    ]
    + [["ALL", base + "_real", "ki", "1", "TRUE"] for base, _ in _KI_BASES]
    + [
        ["", "", "", "", ""],
        ["Area_Code", "Effort_Weight", "Skill_Weight", "KI_Weight", ""],
        ["ALL", "0.33", "0.33", "0.34", ""],
    ],
    columns=["Area_Code", "Metric_Key", "Score_Component", "Weight", "Active"],
)

MISSION_ORG = pd.DataFrame([
    {"Area_Code": "A014", "Area_Name": "Arauco 1", "Zone": "Arauco",
     "District": "Arauco", "Companion1_Name": "Elder Uno",
     "Companion1_Email": "arauco1@missionary.org", "Companion2_Name": "Elder Dos",
     "Companion2_Email": "arauco1@missionary.org", "Is_DL": "FALSE",
     "Is_ZL": "FALSE", "Is_STL": "FALSE", "Is_AP": "FALSE", "Is_MP": "FALSE",
     "Active": "TRUE"},
    {"Area_Code": "A021", "Area_Name": "Lota 2", "Zone": "Arauco",
     "District": "Lota", "Companion1_Name": "Hermana Tres",
     "Companion1_Email": "lota2@missionary.org", "Companion2_Name": "Hermana Cuatro",
     "Companion2_Email": "lota2@missionary.org", "Is_DL": "FALSE",
     "Is_ZL": "FALSE", "Is_STL": "FALSE", "Is_AP": "FALSE", "Is_MP": "FALSE",
     "Active": "TRUE"},
])

_DATES = ["2026-07-27", "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31"]
_NUMERIC_NIGHTLY = [k for k, _, d in _NIGHTLY if d == "NUMBER"]


def _daily_log() -> pd.DataFrame:
    rows = []
    for d in _DATES:
        for area, zone, district in (("Arauco 1", "Arauco", "Arauco"),
                                     ("Lota 2", "Arauco", "Lota")):
            row = {"Date": d, "Area": area, "Zone": zone, "District": district}
            for i, key in enumerate(_NUMERIC_NIGHTLY):
                row[key] = str(3 + i)
            row["exchanges"] = "No"
            row["effort"] = "Todo"
            rows.append(row)
    return pd.DataFrame(rows)


def _weekly_ki() -> pd.DataFrame:
    rows = []
    for week in ("2026-07-19", "2026-07-26"):
        for area, zone, district in (("Arauco 1", "Arauco", "Arauco"),
                                     ("Lota 2", "Arauco", "Lota")):
            row = {"week_end_date": week, "area": area, "zone": zone,
                   "district": district}
            for i, (base, _) in enumerate(_KI_BASES):
                row[base + "_real"] = str(2 + i)
                row[base + "_meta"] = str(3 + i)
            rows.append(row)
    return pd.DataFrame(rows)


def _dashboard_summary() -> pd.DataFrame:
    rows = []
    for key in _NUMERIC_NIGHTLY:
        rows.append({"record_type": "MISSION", "metric_key": key,
                     "metric_name": key, "zone": "", "area": "", "district": "",
                     "val_7d": "40", "val_14d": "80", "val_28d": "160",
                     "val_transfer": "240", "goal_weekly": "50", "date": "",
                     "all_count": "", "most_count": "", "some_count": "",
                     "submitted_count": "", "total_areas": "", "meta_key": "",
                     "meta_value": ""})
        rows.append({"record_type": "ZONE", "metric_key": key,
                     "metric_name": key, "zone": "Arauco", "area": "",
                     "district": "", "val_7d": "20", "val_14d": "40",
                     "val_28d": "80", "val_transfer": "120", "goal_weekly": "",
                     "date": "", "all_count": "", "most_count": "",
                     "some_count": "", "submitted_count": "", "total_areas": "",
                     "meta_key": "", "meta_value": ""})
    for d in _DATES:
        rows.append({"record_type": "EFFORT", "metric_key": "", "metric_name": "",
                     "zone": "", "area": "", "district": "", "val_7d": "",
                     "val_14d": "", "val_28d": "", "val_transfer": "",
                     "goal_weekly": "", "date": d, "all_count": "6",
                     "most_count": "3", "some_count": "1",
                     "submitted_count": "10", "total_areas": "10",
                     "meta_key": "", "meta_value": ""})
    return pd.DataFrame(rows)


def _scores() -> pd.DataFrame:
    return pd.DataFrame([
        {"Area_Code": "A014", "Area_Name": "Arauco 1", "Zone": "Arauco",
         "Missionary_Names": "Elder Uno / Elder Dos",
         "Week_Ending_Date": "2026-07-26", "Effort_Score": "72.5",
         "Skill_Score": "64.0", "KI_Score": "80.0",
         "Effectiveness_Score": "72.2", "Computed_At": "2026-07-26 23:00"},
        {"Area_Code": "A021", "Area_Name": "Lota 2", "Zone": "Arauco",
         "Missionary_Names": "Hermana Tres / Hermana Cuatro",
         "Week_Ending_Date": "2026-07-26", "Effort_Score": "55.0",
         "Skill_Score": "48.5", "KI_Score": "60.0",
         "Effectiveness_Score": "54.5", "Computed_At": "2026-07-26 23:00"},
        # A leadership tracking row. Never a real area — it never submits and
        # scores 0, so leaving it in drags every mission average down.
        {"Area_Code": "ZL01", "Area_Name": "Zone Leader - Arauco", "Zone": "ALL",
         "Missionary_Names": "", "Week_Ending_Date": "2026-07-26",
         "Effort_Score": "0", "Skill_Score": "0", "KI_Score": "0",
         "Effectiveness_Score": "0", "Computed_At": "2026-07-26 23:00"},
    ])


def _live_snapshot() -> pd.DataFrame:
    """One row per area with 7d/14d/28d/transfer totals per nightly metric —
    the shape CCSM_Agent3 rebuilds on every run."""
    rows = []
    for area, zone, district in (("Arauco 1", "Arauco", "Arauco"),
                                 ("Lota 2", "Arauco", "Lota")):
        row = {"Area": area, "Zone": zone, "District": district,
               "Last_Updated": "2026-08-01 06:00"}
        for i, key in enumerate(_NUMERIC_NIGHTLY):
            for window, mult in (("7d", 7), ("14d", 14), ("28d", 28),
                                 ("transfer", 35)):
                row[f"{key}_{window}"] = str((3 + i) * mult)
        rows.append(row)
    return pd.DataFrame(rows)


TRANSFER_SCHEDULE = pd.DataFrame([
    {"Transfer_Number": "1", "Start_Date": "2026-07-27", "Weeks": "6",
     "Status": "Activo"},
])

AGENT_CONFIG = pd.DataFrame([
    {"Key": "MISSION_NAME", "Value": "Chile Concepción South Mission"},
    {"Key": "MISSION_LANGUAGE", "Value": "ES"},
    {"Key": "MISSION_LOCALE", "Value": "es_CL"},
    {"Key": "MISSION_TIMEZONE", "Value": "America/Santiago"},
    {"Key": "TRANSFER_START_DATE", "Value": "2026-07-27"},
])

_TABS = {}


@pytest.fixture(autouse=True)
def _sheets(monkeypatch):
    _TABS.clear()
    _TABS.update({
        "QUESTIONS_CONFIG": _questions_config(),
        "SCORE_CONFIG": SCORE_CONFIG,
        "MISSION_ORG": MISSION_ORG,
        "DAILY_LOG": _daily_log(),
        "WEEKLY_KI": _weekly_ki(),
        "DASHBOARD_SUMMARY": _dashboard_summary(),
        "SCORES": _scores(),
        "LIVE_SNAPSHOT": _live_snapshot(),
        "TRANSFER_SCHEDULE": TRANSFER_SCHEDULE,
        "AGENT_CONFIG": AGENT_CONFIG,
    })

    def fake(tab_name, header_marker=None):
        return _TABS.get(tab_name, pd.DataFrame()).copy()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    _clear_query_caches()
    mc.clear_cache()
    yield
    _clear_query_caches()
    mc.clear_cache()


def _clear_query_caches() -> None:
    """Drop EVERY @st.cache_data memo in the process.

    @st.cache_data keys on argument values, which are identical across test
    files, so an entry another module's fixture populated gets served here
    instead of this file's data. See
    [[feedback-cache-data-pollution-across-pytest-tests]].

    Global, not per-module: the caches that actually broke these tests are
    defined in the PAGE modules (pages/06_Puntajes.py::_load_daily), not in
    app.db.queries. Another test file renders that page against an empty
    DAILY_LOG, `_load_daily(14)` memoises the empty frame, and Daily Activity
    then renders its "no metrics" branch here — every vocabulary assertion
    below passes on a blank section. This test file passed in isolation and
    failed in the full suite until this cleared everything.

    Do NOT narrow this to `hasattr(obj, "clear")` over a module's namespace:
    plain dicts and sets have a `clear` too, so that empties the module's own
    constants (queries._EVEN_COMPOSITION among them) for the rest of the run.
    """
    import streamlit as st

    st.cache_data.clear()


def _text(at) -> str:
    """Every string the rendered page produced, including chart traces.

    Plotly figures matter here: the Dashboard's trend charts and the Daily
    Activity bars carry metric names in their trace names and axis titles, and
    those are exactly where Provo's keys used to survive.
    """
    parts = []
    for attr in ("markdown", "caption", "info", "warning", "error", "success",
                 "button", "radio", "selectbox", "expander", "text_input",
                 "header", "subheader", "title", "metric", "checkbox",
                 "number_input", "text_area", "multiselect", "dataframe",
                 "table", "tabs"):
        for el in getattr(at, attr, []):
            for f in ("value", "label", "body", "placeholder"):
                v = getattr(el, f, None)
                if isinstance(v, str):
                    parts.append(v)
            v = getattr(el, "options", None)
            if isinstance(v, (list, tuple)):
                parts.extend(str(o) for o in v)
    return "\n".join(parts)


def _run(page, lang="es", **state):
    at = AppTest.from_file(page, default_timeout=120)
    at.session_state["pmg_lang"] = lang
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, f"{page} raised: {at.exception}"
    return at


PROVO_KEYS = [
    "lsi_given", "lsi_followups", "nm_doors", "nm_texts", "nm_contacted",
    "nm_meaningful", "nm_lessons", "date_metric", "la_lessons", "locos_Attempt",
    "fellowshipper_Attempt", "aux_Attempt", "info_Attempt", "online_referrals",
    "new_found", "member_lessons", "mmm_sent", "rc_total", "locos_knocked",
]
PROVO_LABELS = [
    "NM Lessons", "LSI Given", "LSI Follow-Ups", "NM Attempted", "NM Contacted",
    "LOCOS Attempted", "MMM Sent", "RC Total", "Online Referrals",
    "Fellowshipped Lessons", "Non-Member Lessons",
]

PAGES = [
    "pages/01_Panel.py",
    "pages/06_Puntajes.py",
    # The Phase 4 pages. Included here rather than only in the "does it render"
    # audit, because those run on empty fixtures and every one of these pages
    # has an empty-state branch that would swallow a vocabulary mistake whole.
    "pages/11_Informes.py",
    "pages/12_Traslados.py",
    "pages/14_Referencias.py",
]


# ── The data actually reaches the page ────────────────────────────────────────

@pytest.mark.parametrize("page", PAGES)
def test_page_is_not_empty(page):
    """Guard for these tests themselves. If a fixture stops feeding a page, the
    vocabulary assertions below would pass on a blank screen — which is the
    exact false green this file exists to close."""
    body = _text(_run(page))
    assert len(body) > 400, f"{page} rendered almost nothing:\n{body}"
    # Every empty-state string a metric section can fall through to. Each one
    # is a way for a vocabulary assertion to pass by rendering nothing at all —
    # "No data for this category" in particular is what the old Provo-keyed
    # Daily Activity groups printed five times over against CCSM's DAILY_LOG.
    for empty_marker in ("No daily activity data yet",
                         "No data for this section yet",
                         "No data for this category",
                         "No data for the selected filters",
                         "nightly metrics appear in DAILY_LOG",
                         "No metrics are configured"):
        assert empty_marker not in body, (
            f"{page} fell through to an empty state ({empty_marker!r}), so "
            f"nothing below this line proves anything about its vocabulary."
        )


def test_traslados_roster_update_tab_renders():
    """The Schedule/Roster Update tab split (2026-08-06) made Schedule the
    default radio selection, so test_page_is_not_empty[pages/12_Traslados.py]
    alone no longer touches the checklist box or the Pull/Preview/Apply/Sync
    UI — those only render when Roster Update is selected. Exercise it
    explicitly, same session_state convention as
    test_goals_duplicate_metric_keys.py's goals_active_section."""
    at = _run("pages/12_Traslados.py", traslados_active_section="Roster Update")
    body = _text(at)
    assert len(body) > 400, f"Roster Update tab rendered almost nothing:\n{body}"
    assert "Lista de verificación del día de traslado" in body
    assert "Extraer organización desde IMOS" in body
    assert "Actualización de emergencia" in body
    leaked = sorted({k for k in PROVO_KEYS if k in body}
                    | {l for l in PROVO_LABELS if l in body})
    assert leaked == [], f"Roster Update tab displays Provo vocabulary: {leaked}"


# ── Vocabulary, against a page with real data on it ───────────────────────────

@pytest.mark.parametrize("page", PAGES)
def test_no_provo_key_or_label_reaches_a_populated_page(page):
    body = _text(_run(page))
    leaked = sorted({k for k in PROVO_KEYS if k in body}
                    | {l for l in PROVO_LABELS if l in body})
    assert leaked == [], f"{page} displays Provo vocabulary: {leaked}"


def test_dashboard_shows_ccsms_key_indicators():
    """The KI row was a fixed Pew / Date / Gate / Renew, all reading 0. Every
    one of CCSM's seven must be named instead."""
    body = _text(_run("pages/01_Panel.py"))
    missing = [label for _, label in _KI_BASES if label not in body]
    assert missing == [], f"Key Indicators absent from the Dashboard: {missing}"


def test_dashboard_nightly_row_shows_scored_metrics():
    """The nightly KPI row and zone leaderboard come from SCORE_CONFIG's effort
    component. `effort` itself is CHOICE and must NOT be offered as a countable
    tile."""
    body = _text(_run("pages/01_Panel.py"))
    for label in ("Intentos de Contacto", "Prácticas de Enseñanza",
                  "Contactos con Miembros"):
        assert label in body, f"{label!r} missing from the Dashboard"


def test_daily_activity_totals_every_nightly_metric():
    """Daily Activity's five hardcoded Provo groups are replaced by the
    catalogue. Every numeric nightly metric must get a Mission Totals tile.

    Asserted against st.metric TILE LABELS, not against the page's whole text.
    Searching the whole body passes for the wrong reason: 06_Puntajes.py's
    Analyze tab builds its picker from the same catalogue, so every CCSM label
    appears somewhere on the page even when Daily Activity itself rendered five
    "No data for this category" panels.
    """
    at = _run("pages/06_Puntajes.py")
    tile_labels = {m.label for m in at.metric}
    missing = [
        label for _key, label, dtype in _NIGHTLY
        if dtype == "NUMBER" and label not in tile_labels
    ]
    assert missing == [], (
        f"Daily Activity omits nightly metrics: {missing}. "
        f"Tiles present: {sorted(tile_labels)}"
    )


def test_daily_activity_excludes_non_numeric_metrics():
    """`effort` is CHOICE and `exchanges` is YESNO. Summing either produces a
    number with no meaning, and _num() would coerce the words to 0 — a real
    zero and an unparseable answer would look identical."""
    at = _run("pages/06_Puntajes.py")
    chart_pickers = [w for w in at.multiselect if w.key == "da_trend_metrics"]
    assert chart_pickers, "Daily Activity's metric picker did not render"

    # AppTest reports options AFTER format_func, so these are display labels,
    # not raw keys — assert against the labels or the check is vacuous.
    options = set(chart_pickers[0].options)
    assert "Nivel de Esfuerzo" not in options, \
        "CHOICE metric offered as a countable metric"
    assert "Intercambios" not in options, \
        "YESNO metric offered as a countable metric"
    assert "Contactos" in options
    assert "Intentos de Contacto" in options


def test_score_editor_universe_is_the_missions_own_metrics():
    """The Score Weight Editor clear-and-rewrites SCORE_CONFIG over exactly the
    universe it renders. With Provo's universe, one Save replaced CCSM's real
    scoring configuration with metrics that do not exist — and reported
    success. Assert the KI tab offers CCSM's seven and nothing else."""
    from app.db.queries import get_score_component_weights

    ki = get_score_component_weights("ki", "ALL")
    assert set(ki) == {base + "_real" for base, _ in _KI_BASES}

    effort = get_score_component_weights("effort", "ALL")
    assert set(effort) == {"contacts_attempted", "roleplays", "member_contacts",
                           "effort"}

    skill = get_score_component_weights("skill", "ALL")
    assert set(skill) == {"contact_rate", "mc_rate", "lesson_rate", "close_rate"}


def test_effectiveness_composition_comes_from_the_sheet():
    """Was Provo's 0.30/0.40/0.30 from member_referral.json. CCSM's SCORE_CONFIG
    says 0.33/0.33/0.34, and that is what CCSM_AgentScores.gs uses — a different
    mix here silently disagrees with every score the agent wrote."""
    from app.db.queries import get_effectiveness_composition_weights

    w = get_effectiveness_composition_weights()
    assert w == pytest.approx({"effort": 0.33, "skill": 0.33, "ki": 0.34})


def test_effectiveness_composition_falls_back_to_an_even_split():
    """Never to a mission's numbers. An empty SCORE_CONFIG means 'unconfigured',
    and the only defensible unconfigured answer is that the three count the
    same."""
    from app.db.queries import get_effectiveness_composition_weights

    get_effectiveness_composition_weights.clear()
    _TABS["SCORE_CONFIG"] = pd.DataFrame()
    w = get_effectiveness_composition_weights()
    assert w == pytest.approx({"effort": 1 / 3, "skill": 1 / 3, "ki": 1 / 3})


def test_flavor_metric_vocabulary_ignores_the_flavor_file():
    """MISSION_FLAVOR is unset, so load_flavor() returns member_referral.json —
    Utah Provo's. Its declared nm_lessons/pew/gate/locos_Attempt vocabulary must
    not survive into any accessor a page reads."""
    from app.config.flavor_loader import flavor

    assert flavor.metric_groups == {}
    for accessor in (flavor.weekly_metrics, flavor.kpi_highlights,
                     flavor.nightly_highlights, flavor.nightly_metrics):
        leaked = sorted(set(accessor) & set(PROVO_KEYS))
        assert leaked == [], f"flavor accessor leaked Provo keys: {leaked}"

    assert set(flavor.kpi_highlights) == {base + "_real" for base, _ in _KI_BASES}
    assert "effort" not in flavor.nightly_highlights, \
        "a CHOICE metric must not be a headline countable tile"


def test_empty_catalogue_renders_nothing_rather_than_a_default():
    """A stale baked-in fallback is how this whole mess started. With no
    QUESTIONS_CONFIG and no SCORE_CONFIG there must be no metric vocabulary at
    all — not Provo's, not anyone's."""
    from app.config.flavor_loader import flavor

    _TABS["QUESTIONS_CONFIG"] = pd.DataFrame()
    _TABS["SCORE_CONFIG"] = pd.DataFrame()
    mc.clear_cache()

    assert flavor.weekly_metrics == []
    assert flavor.kpi_highlights == []
    assert flavor.nightly_metrics == []
    assert flavor.nightly_highlights == []
