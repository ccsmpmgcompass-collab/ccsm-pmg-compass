"""Runtime proof that the pages actually render Spanish.

The coverage gate is a source scan: it proves every literal is routed through
t() and has an ES entry. Neither fact proves a page renders Spanish - a stale
key, surrounding whitespace, or a t() call evaluated before the language is
set would all pass the scan and still show English. These tests read the text
back out of a rendered page instead.
"""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture(autouse=True)
def _empty_sheets(monkeypatch):
    monkeypatch.setattr("app.db.sheets_client._read_tab_cached",
                        lambda *a, **k: pd.DataFrame())


def _text(at) -> str:
    parts = []
    for attr in ("markdown", "caption", "info", "warning", "error", "success",
                 "button", "radio", "selectbox", "expander", "text_input",
                 "header", "subheader", "title", "metric", "checkbox",
                 "text_area", "multiselect"):
        for el in getattr(at, attr, []):
            for f in ("value", "label", "body", "placeholder"):
                v = getattr(el, f, None)
                if isinstance(v, str):
                    parts.append(v)
    return "\n".join(parts)


def _run(page, lang):
    at = AppTest.from_file(page, default_timeout=90)
    at.session_state["pmg_lang"] = lang
    at.run()
    assert not at.exception, f"{page} raised in {lang}: {at.exception}"
    return at


def test_home_renders_spanish():
    es = _text(_run("Home.py", "es"))
    assert "Asistente de la Misión" in es
    assert "Guía de la Aplicación" in es
    assert "Recargar" in es
    assert "Mission Assistant" not in es


def test_home_still_renders_english():
    en = _text(_run("Home.py", "en"))
    assert "Mission Assistant" in en
    assert "Asistente de la Misión" not in en


def test_dashboard_renders_spanish():
    es = _text(_run("pages/01_dashboard.py", "es"))
    assert "Panel Ejecutivo" in es
    assert "Executive Dashboard" not in es


def test_breakdowns_renders_spanish():
    es = _text(_run("pages/04_Breakdowns.py", "es"))
    assert "Desgloses" in es
    assert "Zone, District & Area Performance" not in es


TASK10 = [
    "pages/07_Finding_Funnel.py",
    "pages/10_Notes.py",
    "pages/15_Suggestions.py",
    "pages/17_Action_Center.py",
]


@pytest.mark.parametrize("page", TASK10)
def test_task10_pages_survive_both_languages(page):
    """These four were wrapped by a codemod rather than by hand, so the real
    check is that they still execute - in both languages."""
    for lang in ("en", "es"):
        _run(page, lang)


def test_notes_and_suggestions_render_spanish():
    assert "Filtrar Notas" in _text(_run("pages/10_Notes.py", "es"))
    assert "Sugerencias" in _text(_run("pages/15_Suggestions.py", "es"))


def test_suggestion_status_filter_sends_english_to_the_sheet(monkeypatch):
    """The approval statuses are stored in COMPASS_CCSM and read by the Apps
    Script agents. The dropdown shows Spanish, but the value handed to
    get_suggestions() must still be the English one, or the query matches
    nothing and a write would corrupt the status column."""
    seen = {}

    import app.db.queries as q
    real = q.get_suggestions

    def spy(*a, **k):
        seen.update(k)
        return real(*a, **k)

    monkeypatch.setattr(q, "get_suggestions", spy)
    at = AppTest.from_file("pages/15_Suggestions.py", default_timeout=90)
    at.session_state["pmg_lang"] = "es"
    at.run()
    assert not at.exception
    assert seen.get("status") in (
        "Pending", "AP Approval", "Mission President Approval",
        "Final Approval", "Hold", "Done", "Rejected", "All",
    ), f"a translated status reached the sheet query: {seen.get('status')!r}"


def test_scores_page_renders_spanish():
    es = _text(_run("pages/06_Scores.py", "es"))
    assert "Puntajes" in es


def test_sign_out_is_translated_on_every_page():
    """render_sidebar is shared, so a miss here would leave English chrome on
    all ten pages at once."""
    assert "Cerrar sesión" in _text(_run("Home.py", "es"))


def test_placeholders_are_filled_not_left_raw():
    """A translation that dropped or renamed a {placeholder} would surface as
    literal brace text on the page."""
    for page in ("Home.py", "pages/01_dashboard.py", "pages/04_Breakdowns.py"):
        for lang in ("en", "es"):
            body = _text(_run(page, lang))
            for raw in ("{mission}", "{name}", "{week}", "{scope}", "{n}"):
                assert raw not in body, f"{page} [{lang}] leaked {raw}"
