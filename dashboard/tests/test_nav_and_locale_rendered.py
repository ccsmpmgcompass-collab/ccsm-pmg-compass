"""Phase 3, checked on the rendered product rather than in the source.

Two things a source scan cannot settle:

* what the sidebar will actually say — that comes from Streamlit's own page
  discovery over the real pages/ directory, not from any string in this repo;
* whether a number or date reached the screen in Chilean form, since the
  formatting happens at the call site and the wrong answer is a valid-looking
  number rather than an error.
"""

import re
import unicodedata
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from streamlit.source_util import get_pages

from app.config import metric_catalog as mc
from tests.test_renders_ccsm_with_data import (  # reuse the realistic fixtures
    _daily_log, _dashboard_summary, _questions_config, _weekly_ki,
    MISSION_ORG, SCORE_CONFIG,
)

DASHBOARD = Path(__file__).resolve().parent.parent


# ── Sidebar navigation ────────────────────────────────────────────────────────

#: filename stem -> what the sidebar must read. Streamlit derives the label from
#: the filename (underscores become spaces), so this IS the navigation.
EXPECTED_NAV = {
    "01_Panel.py":              "Panel",
    "02_Metas.py":              "Metas",
    "04_Desgloses.py":          "Desgloses",
    "06_Puntajes.py":           "Puntajes",
    "07_Embudo_de_Búsqueda.py": "Embudo de Búsqueda",
    "10_Notas.py":              "Notas",
    "15_Sugerencias.py":        "Sugerencias",
    "17_Centro_de_Acción.py":   "Centro de Acción",
    "18_Mantenimiento.py":      "Mantenimiento",
}

ENGLISH_NAV_WORDS = ("dashboard", "Goals", "Breakdowns", "Scores",
                     "Finding", "Funnel", "Notes", "Suggestions",
                     "Action", "Center", "Maintenance")


def _discovered_pages():
    return get_pages(str(DASHBOARD / "Home.py"))


def test_sidebar_labels_are_spanish():
    labels = {
        Path(info["script_path"]).name: info["page_name"].replace("_", " ")
        for info in _discovered_pages().values()
    }
    for filename, expected in EXPECTED_NAV.items():
        assert filename in labels, f"{filename} was not discovered by Streamlit"
        assert labels[filename] == expected, \
            f"{filename} renders as {labels[filename]!r}, expected {expected!r}"


def test_no_english_page_name_survives():
    leaked = {
        info["page_name"] for info in _discovered_pages().values()
        if any(w in info["page_name"] for w in ENGLISH_NAV_WORDS)
    }
    assert leaked == set(), f"English nav labels remain: {sorted(leaked)}"


def test_accented_filenames_are_nfc_normalised():
    """`Búsqueda` and `Acción` carry accents, and macOS writes NFD while
    Windows and Linux write NFC. A repo holding one and a checkout expecting the
    other means Streamlit finds no page at that path at all — a blank sidebar
    entry on Cloud that never reproduces locally. Pin the encoding.
    """
    for path in (DASHBOARD / "pages").glob("*.py"):
        assert unicodedata.is_normalized("NFC", path.name), \
            f"{path.name!r} is not NFC-normalised"


def test_every_page_file_is_importable_after_the_rename():
    """A rename that missed a switch_page target fails at click time, not at
    import. tests/test_isolation.py checks the targets resolve; this checks the
    files themselves still parse."""
    import ast
    for path in (DASHBOARD / "pages").glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"))


# ── es_CL conventions on a real page ─────────────────────────────────────────

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
        # The mission declares its own language and locale; nothing may assume.
        "AGENT_CONFIG": pd.DataFrame([
            {"Key": "MISSION_NAME", "Value": "Chile Concepción South Mission"},
            {"Key": "MISSION_LANGUAGE", "Value": "ES"},
            {"Key": "MISSION_LOCALE", "Value": "es_CL"},
            {"Key": "MISSION_TIMEZONE", "Value": "America/Santiago"},
        ]),
    })

    def fake(tab_name, header_marker=None):
        return _TABS.get(tab_name, pd.DataFrame()).copy()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    import streamlit as st
    st.cache_data.clear()
    mc.clear_cache()
    yield
    st.cache_data.clear()
    mc.clear_cache()


def _visible_text(at) -> str:
    """Text a reader actually sees in the KPI cards.

    The cards are one raw-HTML markdown block, so their numbers never reach
    at.metric. Only the TEXT NODES are returned — matching the raw HTML instead
    picks up `rgba(255,255,255,...)` from the inline styles, which looks exactly
    like an anglo-grouped number and makes the assertion below fire on the
    stylesheet rather than on the data.
    """
    html = "\n".join(m.value for m in at.markdown if isinstance(m.value, str))
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"style\s*=\s*\"[^\"]*\"", " ", html)
    return " ".join(re.findall(r">([^<>]+)<", html))


def _big_number_summary() -> pd.DataFrame:
    """DASHBOARD_SUMMARY whose values are large enough to exercise thousands
    grouping. The shared fixture tops out in the hundreds, so a separator bug
    would leave no trace on it at all."""
    df = _dashboard_summary()
    mission = df["record_type"] == "MISSION"
    df.loc[mission, "val_7d"] = "12345"
    df.loc[mission, "goal_weekly"] = "20000"
    return df


def test_kpi_numbers_use_chilean_separators():
    """render_kpi_row hardcoded f"{int(value):,}". A Chilean reader parses
    "12,345" as twelve point three four five — off by a factor of a thousand,
    and it looks like a perfectly ordinary number."""
    _TABS["DASHBOARD_SUMMARY"] = _big_number_summary()

    at = AppTest.from_file("pages/01_Panel.py", default_timeout=120)
    at.session_state["pmg_lang"] = "es"
    at.run()
    assert not at.exception, at.exception

    text = _visible_text(at)
    assert "12.345" in text, (
        "the Chilean form of 12345 is not on the page; visible text was:\n"
        + text[:2000]
    )
    anglo = re.findall(r"\b\d{1,3},\d{3}\b", text)
    assert anglo == [], f"anglo thousands separators reached the screen: {anglo}"


def test_kpi_numbers_stay_anglo_in_english():
    """The switch is real, not a one-way rewrite."""
    _TABS["DASHBOARD_SUMMARY"] = _big_number_summary()

    at = AppTest.from_file("pages/01_Panel.py", default_timeout=120)
    at.session_state["pmg_lang"] = "en"
    at.run()
    assert not at.exception, at.exception
    assert "12,345" in _visible_text(at)


def test_language_defaults_to_spanish_from_agent_config():
    """MISSION_LANGUAGE is ES. Nobody should have to find the toggle to read
    their own mission's dashboard in their own language."""
    at = AppTest.from_file("pages/01_Panel.py", default_timeout=120)
    at.run()          # deliberately NOT setting pmg_lang
    assert not at.exception, at.exception
    assert at.session_state["pmg_lang_default"] == "es"


def test_spanish_page_shows_no_english_month_names():
    """strftime('%B')/'%b' emit English whatever the interface language is."""
    at = AppTest.from_file("pages/02_Metas.py", default_timeout=120)
    at.session_state["pmg_lang"] = "es"
    at.run()
    assert not at.exception, at.exception

    body = "\n".join(
        str(getattr(el, f, "") or "")
        for attr in ("markdown", "caption", "info", "subheader", "expander",
                     "button", "selectbox", "radio")
        for el in getattr(at, attr, [])
        for f in ("value", "label", "body")
    )
    english_months = [
        m for m in ("January", "February", "March", "April", "June", "July",
                    "August", "September", "October", "November", "December")
        if re.search(rf"\b{m}\b", body)
    ]
    assert english_months == [], \
        f"English month names on a Spanish page: {english_months}"
