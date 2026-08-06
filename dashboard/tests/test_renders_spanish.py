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
    es = _text(_run("pages/01_Panel.py", "es"))
    assert "Panel Ejecutivo" in es
    assert "Executive Dashboard" not in es


def test_breakdowns_renders_spanish():
    es = _text(_run("pages/04_Desgloses.py", "es"))
    assert "Desgloses" in es
    assert "Zone, District & Area Performance" not in es


def _all_pages() -> list[str]:
    """Every page in the app, discovered rather than listed.

    This was a hardcoded list, which meant a page added later was not audited
    in either language until somebody remembered to add it here — and the
    symptom of forgetting is a silently unchecked page, not a failure. Reading
    the directory makes coverage automatic.
    """
    from pathlib import Path
    pages_dir = Path(__file__).resolve().parent.parent / "pages"
    found = sorted(
        f"pages/{p.name}" for p in pages_dir.glob("*.py")
        if p.name != "__init__.py"
    )
    return ["Home.py"] + found


ALL_PAGES = _all_pages()


@pytest.mark.parametrize("page", ALL_PAGES)
def test_every_page_survives_both_languages(page):
    """Most of these were wrapped by a codemod rather than by hand, so the
    real check is that all ten still execute - in both languages."""
    for lang in ("en", "es"):
        _run(page, lang)


def test_notes_and_suggestions_render_spanish():
    assert "Filtrar Notas" in _text(_run("pages/10_Notas.py", "es"))
    assert "Sugerencias" in _text(_run("pages/15_Sugerencias.py", "es"))


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
    at = AppTest.from_file("pages/15_Sugerencias.py", default_timeout=90)
    at.session_state["pmg_lang"] = "es"
    at.run()
    assert not at.exception
    assert seen.get("status") in (
        "Pending", "AP Approval", "Mission President Approval",
        "Final Approval", "Hold", "Done", "Rejected", "All",
    ), f"a translated status reached the sheet query: {seen.get('status')!r}"


def test_scores_page_renders_spanish():
    es = _text(_run("pages/06_Puntajes.py", "es"))
    assert "Puntajes" in es


def test_sign_out_is_translated_on_every_page():
    """render_sidebar is shared, so a miss here would leave English chrome on
    all ten pages at once."""
    assert "Cerrar sesión" in _text(_run("Home.py", "es"))


@pytest.mark.parametrize("page", ALL_PAGES)
def test_placeholders_are_filled_not_left_raw(page):
    """A translation that dropped or renamed a {placeholder} surfaces as
    literal brace text on the page.

    Matched by pattern rather than against a fixed list of field names: the
    f-string conversion introduced ~109 new ones, and a hardcoded list is
    exactly the kind of check that silently stops covering what it names.
    """
    import re
    for lang in ("en", "es"):
        body = _text(_run(page, lang))
        # Drop <style> blocks first: a CSS rule body is also brace-delimited,
        # and it is markup rather than copy - the same reason the extractor
        # refuses to treat a stylesheet as a translatable string.
        body = re.sub(r"<style>.*?</style>", "", body, flags=re.S)
        # A real placeholder is a bare identifier with at most a short format
        # spec; anything with a semicolon or whitespace is CSS or prose.
        leaked = sorted(set(re.findall(r"\{[a-z_][a-z0-9_]*(?:[!:][^};\s]{0,12})?\}", body)))
        assert leaked == [], f"{page} [{lang}] leaked {leaked}"


def test_every_translation_keeps_its_placeholders():
    """A Spanish string that dropped or renamed a {placeholder} raises at
    format() time and t() silently falls back to English - the page still
    renders, so nothing would surface this at runtime."""
    import re
    from app.i18n.es import ES

    def fields(s):
        return set(re.findall(r"\{(\w+)\}", s))

    bad = [(en, es) for en, es in ES.items() if fields(en) != fields(es)]
    assert bad == [], f"placeholder mismatch: {bad[:5]}"
