"""Pages must render CCSM's metrics — not survive by rendering nothing.

tests/test_renders_spanish.py mocks every sheet read to an EMPTY DataFrame, so
its "every page survives both languages" check passes on a dashboard whose
entire metric catalogue is wrong: with no data there are no metric labels to be
wrong about. That is how a full set of Utah Provo metric keys (nm_lessons,
lsi_given, pew, gate, renew, locos_Attempt …) sat in this app while the suite
stayed green.

These tests feed a realistic QUESTIONS_CONFIG and matching data, then read text
back out of the RENDERED page and assert CCSM's vocabulary is present and
Provo's is absent. Same lesson as tests/test_renders_spanish.py itself: a source
scan cannot prove what a page displays.
"""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app.config import metric_catalog as mc

# A faithful slice of the live QUESTIONS_CONFIG (probe_live.py questions).
QUESTIONS = pd.DataFrame([
    {"Question_ID": "Q-N-001", "Form_Type": "NIGHTLY",
     "Form_Column_Header": "¿Qué fecha está ingresando?",
     "Metric_Key": "report_date", "Metric_Display_Name": "Fecha del Informe",
     "Data_Type": "DATE", "Active": "TRUE"},
    {"Question_ID": "Q-N-004", "Form_Type": "NIGHTLY",
     "Form_Column_Header": "Intentos de contacto con amigos",
     "Metric_Key": "contacts_attempted", "Metric_Display_Name": "Intentos de Contacto",
     "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Question_ID": "Q-N-005", "Form_Type": "NIGHTLY",
     "Form_Column_Header": "Contactos con amigos",
     "Metric_Key": "contacts_made", "Metric_Display_Name": "Contactos",
     "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Question_ID": "Q-N-006", "Form_Type": "NIGHTLY",
     "Form_Column_Header": "Conversaciones significativas con amigos",
     "Metric_Key": "meaningful_conversations",
     "Metric_Display_Name": "Conversaciones Significativas",
     "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Question_ID": "Q-N-018", "Form_Type": "NIGHTLY",
     "Form_Column_Header": "Copias del Libro de Mormón entregadas",
     "Metric_Key": "bom_shared", "Metric_Display_Name": "Libros de Mormón Entregados",
     "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Question_ID": "Q-W-004", "Form_Type": "WEEKLY",
     "Form_Column_Header": "Nuevas personas encontradas (Real)",
     "Metric_Key": "ki_new_people_real",
     "Metric_Display_Name": "Nuevas Personas Encontradas (Real)",
     "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Question_ID": "Q-W-014", "Form_Type": "WEEKLY",
     "Form_Column_Header": "Bautizados y confirmados (Real)",
     "Metric_Key": "ki_baptized_confirmed_real",
     "Metric_Display_Name": "Bautizados y Confirmados (Real)",
     "Data_Type": "NUMBER", "Active": "TRUE"},
])

PROVO_LABELS = [
    "NM Lessons", "LSI Given", "LSI Follow-Ups", "NM Attempted", "NM Contacted",
    "Meaningful Contacts", "LOCOS Attempted", "Fellowshipper Attempted",
    "Aux/Coord Attempted", "Informational Attempted", "MMM Sent",
    "LA Lessons", "RC Total", "Online Referrals",
]
PROVO_KEYS = [
    "nm_lessons", "lsi_given", "nm_doors", "locos_Attempt", "mmm_sent",
    "new_found", "member_lessons", "date_metric", "rc_total",
]


# Sections that pick an area need a roster to pick from. CCSM's real
# MISSION_ORG columns — note there is no Language_Type.
MISSION_ORG = pd.DataFrame([
    {"Area_Code": "A014", "Area_Name": "Arauco 1", "Zone": "Arauco",
     "District": "Arauco", "Companion1_Name": "Elder Uno",
     "Companion1_Email": "arauco1@missionary.org", "Companion2_Name": "Elder Dos",
     "Companion2_Email": "arauco1@missionary.org", "Is_DL": "FALSE",
     "Is_ZL": "FALSE", "Is_STL": "FALSE", "Is_AP": "FALSE", "Is_MP": "FALSE",
     "Active": "TRUE"},
])


@pytest.fixture(autouse=True)
def _sheets(monkeypatch):
    def fake(tab_name, header_marker=None):
        if tab_name == "QUESTIONS_CONFIG":
            return QUESTIONS.copy()
        if tab_name == "MISSION_ORG":
            return MISSION_ORG.copy()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    mc.clear_cache()
    yield
    mc.clear_cache()


def _text(at) -> str:
    parts = []
    for attr in ("markdown", "caption", "info", "warning", "error", "success",
                 "button", "radio", "selectbox", "expander", "text_input",
                 "header", "subheader", "title", "metric", "checkbox",
                 "number_input", "text_area", "multiselect", "dataframe", "table"):
        for el in getattr(at, attr, []):
            for f in ("value", "label", "body", "placeholder"):
                v = getattr(el, f, None)
                if isinstance(v, str):
                    parts.append(v)
            for f in ("options",):
                v = getattr(el, f, None)
                if isinstance(v, (list, tuple)):
                    parts.extend(str(o) for o in v)
    return "\n".join(parts)


def _run(page, lang="es"):
    at = AppTest.from_file(page, default_timeout=90)
    at.session_state["pmg_lang"] = lang
    at.run()
    assert not at.exception, f"{page} raised: {at.exception}"
    return at


# ── The catalogue itself, against a realistic config ──────────────────────────

def test_catalogue_is_ccsms_vocabulary():
    keys = set(mc.metric_options())
    assert "contacts_attempted" in keys
    assert "meaningful_conversations" in keys
    assert "ki_baptized_confirmed_real" in keys
    assert not (keys & set(PROVO_KEYS)), sorted(keys & set(PROVO_KEYS))


def test_goal_to_actual_points_at_metrics_that_exist():
    """Every mission goal must map to a Key Indicator the weekly form collects.
    Provo's mapping pointed at gate/pew/renew/new_found/member_lessons, so each
    goal compared its target against a column that was never in the data and
    read as zero forever — visibly plausible, silently meaningless.

    Checked against the LIVE QUESTIONS_CONFIG snapshot, not this file's fixture:
    the fixture holds two KIs for brevity, and the real question is whether the
    mapping matches the mission's actual seven.
    """
    import json
    from pathlib import Path

    from app.config.flavor_loader import GOAL_TO_ACTUAL

    snap = (Path(__file__).resolve().parent.parent.parent
            / "tests" / "live" / "live_form_headers.json")
    if not snap.exists():
        pytest.skip(f"live snapshot missing: {snap}")
    grid = json.loads(snap.read_text(encoding="utf-8").lstrip("﻿"))
    rows = grid.get("QUESTIONS_CONFIG") or []
    header = [str(c).strip() for c in rows[0]]
    ki, ft = header.index("Metric_Key"), header.index("Form_Type")
    weekly = {str(r[ki]).strip() for r in rows[1:]
              if len(r) > ft and str(r[ft]).strip().upper() == "WEEKLY"}

    broken = {g: a for g, a in GOAL_TO_ACTUAL.items() if a not in weekly}
    assert broken == {}, f"goals mapped to metrics the weekly form lacks: {broken}"


def test_metric_labels_resolve_instead_of_falling_through_to_raw_keys():
    """METRIC_LABELS.get(k, k) means a wrong catalogue never raises — it just
    prints the raw key. Assert the label is genuinely different from the key."""
    from app.config.flavor_loader import METRIC_LABELS
    for key in ("contacts_attempted", "meaningful_conversations", "bom_shared"):
        label = METRIC_LABELS.get(key, key)
        assert label != key, f"{key} fell through to its raw key"
        assert "_" not in label, f"{key} rendered as snake_case: {label}"


# ── Rendered pages ────────────────────────────────────────────────────────────

PAGES = [
    "pages/01_Panel.py",
    "pages/02_Metas.py",
    "pages/04_Desgloses.py",
    "pages/06_Puntajes.py",
    "pages/18_Mantenimiento.py",
]


@pytest.mark.parametrize("page", PAGES)
def test_no_provo_metric_label_reaches_the_screen(page):
    body = _text(_run(page))
    leaked = sorted({p for p in PROVO_LABELS if p in body})
    assert leaked == [], f"{page} displays Provo metric label(s): {leaked}"


@pytest.mark.parametrize("page", PAGES)
def test_no_raw_provo_key_reaches_the_screen(page):
    body = _text(_run(page))
    leaked = sorted({k for k in PROVO_KEYS if k in body})
    assert leaked == [], f"{page} displays Provo metric key(s): {leaked}"


def test_monthly_goals_offers_every_key_indicator():
    """The Monthly Goals section used to pick its boxes by KEYWORD — matching
    "gate", "date", "renew", "pew" anywhere in a metric's key or label, plus the
    exact keys "new_found" and "member_lessons".

    Against CCSM's metrics that collapses to exactly ONE box: nothing matches
    gate/renew/pew/new_found/member_lessons, and "date" matches
    `ki_baptismal_date_real` purely by coincidence of spelling. A single
    arbitrary indicator would have rendered under the heading "Monthly Goals",
    looking entirely deliberate.
    """
    at = AppTest.from_file("pages/02_Metas.py", default_timeout=90)
    at.session_state["pmg_lang"] = "es"
    at.session_state["goals_active_section"] = "Area Goal Customization"
    at.run()
    assert not at.exception, at.exception

    monthly = [w for w in at.number_input if w.key and w.key.startswith("mgoal_")]
    labels = {w.label for w in monthly}

    # Both KIs in this file's QUESTIONS fixture must appear, not just the one
    # whose name happens to contain an English keyword.
    assert any("Nuevas Personas" in l for l in labels), \
        f"KI missing from Monthly Goals. Saw: {sorted(labels)}"
    assert any("Bautizados" in l for l in labels), \
        f"KI missing from Monthly Goals. Saw: {sorted(labels)}"
    assert len(monthly) == 2, \
        f"expected one box per Key Indicator, got {len(monthly)}: {sorted(labels)}"


def test_goals_offers_ccsm_metrics_by_name():
    """The Goals page builds its inputs from the catalogue, so this is the
    end-to-end proof that a QUESTIONS_CONFIG edit reaches a rendered widget."""
    at = AppTest.from_file("pages/02_Metas.py", default_timeout=90)
    at.session_state["pmg_lang"] = "es"
    at.session_state["goals_active_section"] = "Mission Goals"
    at.run()
    assert not at.exception, at.exception

    labels = {w.label for w in at.number_input}
    assert any("Conversaciones Significativas" in l for l in labels), \
        f"CCSM metric not offered on Goals. Saw: {sorted(labels)[:15]}"
    assert not any("NM " in l or "LSI" in l for l in labels), \
        f"Provo metric offered on Goals: {sorted(labels)}"
