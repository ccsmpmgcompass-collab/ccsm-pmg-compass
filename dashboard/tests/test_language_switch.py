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
    at = AppTest.from_file("pages/01_Panel.py", default_timeout=60)
    at.session_state["pmg_lang"] = "es"
    at.run()
    assert not at.exception
    assert at.session_state["pmg_lang"] == "es"


def test_mirrored_switches_agree_after_one_is_changed():
    """Home and the sidebar render the SAME control twice under different
    widget keys, and Streamlit stores each widget's value independently.
    They agree only because `index` is recomputed from the active language
    and counts toward widget identity, so the untouched mirror is re-created
    with the corrected default. If that behavior ever changes, the untouched
    mirror would report the old language and drive it back - an endless rerun
    between the two. Assert both mirrors read Spanish after one was clicked."""
    at = AppTest.from_file("Home.py", default_timeout=60)
    at.run()
    assert len(at.radio) >= 2, "expected a language radio on Home and in the sidebar"
    at.radio[0].set_value("Español").run()
    assert at.session_state["pmg_lang"] == "es"
    assert [r.value for r in at.radio] == ["Español", "Español"], \
        f"mirrors disagree: {[r.value for r in at.radio]}"
