import pytest
import streamlit as st

from app.i18n import t, get_lang, set_lang
from app.i18n.es import ES


@pytest.fixture(autouse=True)
def _clear_state():
    """Reset session state AND the ES dict around every test.

    Several tests below inject translations into ES to exercise lookup. ES is a
    module-level dict, so without this restore those injections would persist
    for the whole pytest session and the Task 9-12 coverage tests would count
    real UI strings ("Area Scores") as translated when they are not.
    """
    original = dict(ES)
    st.session_state.clear()
    yield
    st.session_state.clear()
    ES.clear()
    ES.update(original)


def test_defaults_to_english():
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


def test_set_lang_rejects_unknown():
    with pytest.raises(ValueError):
        set_lang("fr")
