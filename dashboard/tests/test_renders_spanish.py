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
                 "button", "radio", "selectbox", "expander", "text_input"):
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


def test_placeholders_are_filled_not_left_raw():
    """A translation that dropped or renamed a {placeholder} would surface as
    literal brace text on the page."""
    for page in ("Home.py", "pages/01_dashboard.py", "pages/04_Breakdowns.py"):
        for lang in ("en", "es"):
            body = _text(_run(page, lang))
            for raw in ("{mission}", "{name}", "{week}", "{scope}", "{n}"):
                assert raw not in body, f"{page} [{lang}] leaked {raw}"
