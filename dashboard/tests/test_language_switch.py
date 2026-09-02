import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture(autouse=True)
def _empty_sheets(monkeypatch):
    monkeypatch.setattr("app.db.sheets_client._read_tab_cached",
                        lambda *a, **k: pd.DataFrame())


def test_home_renders_a_language_switch():
    at = AppTest.from_file("Home.py", default_timeout=60)
    at.run()
    assert not at.exception
    labels = [r.label for r in at.radio]
    assert any("Language" in (lbl or "") or "Idioma" in (lbl or "")
               for lbl in labels), f"no language radio found: {labels}"


def test_switch_sets_session_state():
    at = AppTest.from_file("Home.py", default_timeout=60)
    at.run()
    at.radio[0].set_value("Español").run()
    assert at.session_state["pmg_lang"] == "es"


def test_language_persists_to_another_page():
    at = AppTest.from_file("views/01_Panel.py", default_timeout=60)
    at.session_state["pmg_lang"] = "es"
    at.run()
    assert not at.exception
    assert at.session_state["pmg_lang"] == "es"


def test_there_is_exactly_one_language_switch():
    """Until 2026-09-02 this control was rendered TWICE — once at the top of
    Home and once in the sidebar — under two different widget keys, which
    Streamlit stores independently. The two only ever agreed because `index`
    is recomputed from the active language on each run and counts toward
    widget identity, so the untouched mirror got re-created with the corrected
    default; the test here used to pin exactly that, because if Streamlit's
    identity rule changed, the stale mirror would report the old language and
    drive it back, in an endless rerun between the two.

    The navigation rebuild removed Home's copy (the sidebar one is visible
    from every page, so the second was duplicate chrome — audit step 1.6).
    That deletes the failure mode rather than defending against it, so what is
    worth pinning now is that the duplicate does not come back."""
    at = AppTest.from_file("Home.py", default_timeout=60)
    at.run()
    lang_radios = [r for r in at.radio
                   if "Language" in (r.label or "") or "Idioma" in (r.label or "")]
    assert len(lang_radios) == 1, \
        f"expected exactly one language switch, found {len(lang_radios)}"
    lang_radios[0].set_value("Español").run()
    assert at.session_state["pmg_lang"] == "es"
