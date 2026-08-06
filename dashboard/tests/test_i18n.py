import pytest
import streamlit as st

from app.i18n import t, get_lang, set_lang
from app.i18n.es import ES


@pytest.fixture(autouse=True)
def _clear_state(monkeypatch):
    """Reset session state AND the ES dict around every test.

    Several tests below inject translations into ES to exercise lookup. ES is a
    module-level dict, so without this restore those injections would persist
    for the whole pytest session and the Task 9-12 coverage tests would count
    real UI strings ("Area Scores") as translated when they are not.

    AGENT_CONFIG is stubbed to silence because get_lang() now resolves its
    default from MISSION_LANGUAGE. Unstubbed, these tests read the LIVE
    COMPASS_CCSM sheet (secrets.toml is present locally), which makes a unit
    test network-dependent and makes its result depend on a mission's
    configuration. Tests that care about the default set it explicitly.
    """
    original = dict(ES)
    st.session_state.clear()
    monkeypatch.setattr("app.db.queries.get_config_value",
                        lambda key, default="": default)
    yield
    st.session_state.clear()
    ES.clear()
    ES.update(original)


def test_defaults_to_the_missions_language():
    """The default is the mission's own MISSION_LANGUAGE, not a hardcoded
    "en" — see app/i18n/mission_default_lang. With the config silent (this
    file's fixture) it degrades to English, which is what is asserted here;
    tests/test_formats_es_cl.py pins the ES case."""
    assert get_lang() == "en"


def test_english_returns_source_unchanged():
    assert t("Area Scores") == "Area Scores"


def test_spanish_returns_translation():
    set_lang("es")
    ES["Area Scores"] = "Puntajes por Área"
    assert t("Area Scores") == "Puntajes por Área"


def test_missing_translation_falls_back_to_english():
    """The core safety property: a missing key must never raise or leak a
    key name - it degrades to readable English."""
    set_lang("es")
    assert t("A string nobody translated") == "A string nobody translated"


def test_interpolation_applies_after_lookup():
    set_lang("es")
    ES["Welcome back, {name}"] = "Bienvenido de nuevo, {name}"
    assert t("Welcome back, {name}", name="Elder Fox") == \
        "Bienvenido de nuevo, Elder Fox"


def test_interpolation_works_in_english_too():
    assert t("Welcome back, {name}", name="Elder Fox") == \
        "Welcome back, Elder Fox"


def test_triple_quoted_block_resolves_despite_surrounding_newlines():
    """The extractor keys ES on the STRIPPED string, but a triple-quoted
    literal reaches t() with its leading/trailing newlines intact. Without a
    stripped-key fallback every such block would silently render English
    while the coverage gate reported it fully translated."""
    set_lang("es")
    ES["**Overview**\n- Home"] = "**Resumen**\n- Inicio"
    assert t("\n**Overview**\n- Home\n") == "\n**Resumen**\n- Inicio\n"


def test_surrounding_whitespace_is_preserved():
    """Markdown spacing is load-bearing - the block must not come back
    stripped, or list and heading rendering shifts."""
    set_lang("es")
    ES["Hello"] = "Hola"
    assert t("\n\nHello\n") == "\n\nHola\n"


def test_exact_key_still_wins_over_stripped():
    set_lang("es")
    ES["\nHello\n"] = "EXACT"
    ES["Hello"] = "STRIPPED"
    assert t("\nHello\n") == "EXACT"


def test_set_lang_rejects_unknown():
    with pytest.raises(ValueError):
        set_lang("fr")
